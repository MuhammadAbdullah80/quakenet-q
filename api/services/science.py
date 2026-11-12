"""Read computations and the QAOA job, composed from the scientific core in src/.

Mirrors run_experiment.py. Results are plain dicts of Python numbers; nothing here knows about HTTP.
"""
from __future__ import annotations

import threading
import time
import warnings
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.stats import spearmanr

from src.baselines import backward_elimination, expert_rule, greedy_forward, simulated_annealing
from src.geometry import Instance, Scorer
from src.location import dn_score, location_errors
from src.qubo import build_objective, energies, to_hamiltonian

from .events import EventRegistry, Loaded

TOP_NETWORKS = 20     # networks listed by the scoring endpoint
TOP_M = 10            # sampled networks re-scored classically
SA_SEEDS = 5
LOC_TRIALS = 3       # noise draws per aftershock in the location test; same as run_experiment.py,
                     # so the console shows the numbers in the report
Sites = tuple[int, ...]


class Cache:
    """Small thread-safe LRU. One computation at a time, so a result is never computed twice."""

    def __init__(self, size: int):
        self._size, self._data, self._lock = size, OrderedDict(), threading.Lock()

    def get(self, key, compute: Callable[[], object]):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            value = self._data[key] = compute()
            while len(self._data) > self._size:
                self._data.popitem(last=False)
            return value


@dataclass(frozen=True)
class EventContext:
    loaded: Loaded
    inst: Instance
    design: Scorer        # scores on the aftershocks known at decision time (used to plan)
    valid: Scorer         # scores on later aftershocks (used to test)
    sets: list[Sites]
    d_empty: float


@dataclass(frozen=True)
class LamContext:
    lam: float
    f_true: np.ndarray    # true objective of every feasible network, in the order of `sets`
    exact: Sites

    def rank(self, value: float) -> int:
        return int((self.f_true > value + 1e-9).sum()) + 1


def _index(sel) -> int:
    return sum(1 << i for i in sel)


def _sites(sel) -> list[int]:
    return sorted(int(i) for i in sel)


class ScienceService:
    def __init__(self, registry: EventRegistry):
        self._registry = registry
        self._events, self._lams = Cache(8), Cache(32)
        self._instances, self._scoring, self._baselines = Cache(8), Cache(32), Cache(32)
        self._loc = Cache(512)        # location test per network: does not depend on lam

    # ------------------------------------------------------------------ shared, cached building blocks
    def _event(self, event_id: str) -> EventContext:
        spec = self._registry.get(event_id)          # raises NotFound for anything not on the allowlist

        def build() -> EventContext:
            loaded = spec.load()
            inst = loaded.inst
            design = Scorer(inst, np.asarray(inst.design, float)[:, :3])
            valid = Scorer(inst, np.asarray(inst.valid, float).reshape(-1, np.shape(inst.design)[1])[:, :3])
            return EventContext(loaded, inst, design, valid, inst.feasible_sets(), design.d_score([]))
        return self._events.get(event_id, build)

    @staticmethod
    def _true_obj(ctx: EventContext, lam: float, sel) -> float:
        """The objective we care about, computed directly (not through the expansion)."""
        sel = list(sel)
        return ctx.design.d_score(sel) - lam * float(ctx.inst.risk[sel].sum()) - ctx.d_empty

    def _lam(self, event_id: str, ctx: EventContext, lam: float) -> LamContext:
        def build() -> LamContext:
            f = np.array([self._true_obj(ctx, lam, s) for s in ctx.sets])
            return LamContext(lam, f, ctx.sets[int(f.argmax())])
        return self._lams.get((event_id, lam), build)

    def _loc_error(self, event_id: str, ctx: EventContext, sel: Sites) -> float:
        return self._loc.get((event_id, tuple(sel)), lambda: float(
            location_errors(ctx.inst, tuple(sel), ctx.inst.valid, trials=LOC_TRIALS).mean()))

    # ------------------------------------------------------------------ read endpoints
    def instance(self, event_id: str) -> dict:
        ctx, spec = self._event(event_id), self._registry.get(event_id)

        def r(v) -> float:                           # metre precision is plenty for a map
            return round(float(v), 3)

        def build() -> dict:
            inst, loaded = ctx.inst, ctx.loaded

            def latlon(x, y) -> dict:
                lat, lon = loaded.to_latlon(float(x), float(y))
                return dict(lat=round(float(lat), 5), lon=round(float(lon), 5))
            return dict(
                event_id=event_id, n=inst.n, k=inst.k, decision_hours=spec.decision_hours,
                mainshock=dict(zip(("x", "y", "depth"), map(r, list(inst.mainshock)[:3]))),
                design_events=[[r(v) for v in e[:3]] for e in inst.design],
                valid_events=[[r(v) for v in e[:3]] for e in inst.valid],
                stations=[dict(name=str(n), x=r(x), y=r(y)) for n, (x, y) in zip(inst.station_names, inst.stations)],
                candidates=[dict(id=i, x=r(x), y=r(y), risk=round(float(c), 4), **latlon(x, y))
                            for i, ((x, y), c) in enumerate(zip(inst.candidates, inst.risk))],
                grid=dict(lat0=float(loaded.lat0), lon0=float(loaded.lon0)),
                feasibility_checked=bool(loaded.feasibility_checked))
        return self._instances.get(event_id, build)

    def scoring(self, event_id: str, lam: float) -> dict:
        ctx = self._event(event_id)
        lc = self._lam(event_id, ctx, lam)

        def build() -> dict:
            inst, sets, f_true = ctx.inst, ctx.sets, lc.f_true
            fidelity = []
            for order in (2, 3, 4):
                obj = build_objective(inst, ctx.design, lam, order)
                f = np.array([obj.value(s) for s in sets])
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    rho = float(spearmanr(f, f_true)[0])
                fidelity.append(dict(order=order, terms=len(obj.terms), spearman=rho if np.isfinite(rho) else 0.0,
                                     max_abs_error=float(np.abs(f - f_true).max()),
                                     rank_of_its_optimum=lc.rank(float(f_true[f.argmax()]))))
            best = np.argsort(-f_true, kind="stable")[:TOP_NETWORKS]
            top = [dict(sites=_sites(sets[i]), objective=float(f_true[i]),
                        risk=float(inst.risk[list(sets[i])].sum()), blur_km=ctx.valid.blur_km(sets[i]),
                        rank=lc.rank(float(f_true[i]))) for i in best]
            return dict(lam=lam, feasible_networks=len(sets), fidelity=fidelity,
                        exact_optimum=_sites(lc.exact), top_networks=top)
        return self._scoring.get((event_id, lam), build)

    def baselines(self, event_id: str, lam: float) -> dict:
        ctx = self._event(event_id)
        lc = self._lam(event_id, ctx, lam)

        def true_obj(sel) -> float:
            return self._true_obj(ctx, lam, sel)

        def build() -> dict:
            inst, sets, n, k = ctx.inst, ctx.sets, ctx.inst.n, ctx.inst.k
            centre = inst.design[:, :2].mean(axis=0)
            dn = np.array([dn_score(inst, s, inst.design) for s in sets])
            picks = {
                "Exact (brute force)": lc.exact,
                "Greedy forward": greedy_forward(n, k, true_obj),
                "Backward elimination": backward_elimination(n, k, true_obj),
                "Simulated annealing": max((simulated_annealing(n, k, true_obj, seed=s) for s in range(SA_SEEDS)),
                                           key=true_obj),
                "Expert rule (azimuthal gap)": expert_rule(inst.stations, inst.candidates, centre, k),
                "Best by D_N criterion": sets[int(dn.argmax())],
            }
            methods = []
            for name, sel in picks.items():
                value = true_obj(sel)
                methods.append(dict(name=name, sites=_sites(sel), objective=value, rank=lc.rank(value),
                                    risk=float(inst.risk[list(sel)].sum()), blur_km=ctx.valid.blur_km(sel),
                                    loc_error_mean_km=self._loc_error(event_id, ctx, tuple(_sites(sel)))))
            return dict(lam=lam, methods=methods,
                        no_new_sensors=dict(blur_km=ctx.valid.blur_km([]),
                                            loc_error_mean_km=self._loc_error(event_id, ctx, ())))
        return self._baselines.get((event_id, lam), build)

    # ------------------------------------------------------------------ the quantum job
    def qaoa(self, event_id: str, *, reps: int, seed: int, shots: int, lam: float, restarts: int,
             maxiter: int, solver: Callable) -> dict:
        """Exact objective -> Hamiltonian -> XY-mixer QAOA -> re-score the most frequent samples."""
        t0 = time.time()
        ctx = self._event(event_id)
        lc = self._lam(event_id, ctx, lam)
        k, sets = ctx.inst.k, ctx.sets
        exact = build_objective(ctx.inst, ctx.design, lam, order=4)
        h, const = to_hamiltonian(exact)
        e_all = energies(exact)
        feas_idx = np.array([_index(s) for s in sets])
        e_feas = e_all[feas_idx]

        run = solver(h, k, reps, seed=seed, restarts=restarts, shots=shots, maxiter=maxiter)

        counts = run["counts"]
        top = [s for s in sorted(counts, key=counts.get, reverse=True) if len(s) == k][:TOP_M]
        if not top:
            raise RuntimeError("the sampler returned no network with exactly k sites")
        scored = []
        for sel in top:
            value = self._true_obj(ctx, lam, sel)
            scored.append(dict(sites=_sites(sel), count=int(counts[sel]), objective=value, rank=lc.rank(value)))
        final = max(scored, key=lambda t: t["objective"])
        exact_sites = _sites(lc.exact)
        probs = np.asarray(run["probs"])
        return dict(
            reps=reps, seed=seed, shots=shots, lam=lam, seconds=round(time.time() - t0, 1),
            ratio=float((e_feas.max() - (run["energy"] + const)) / (e_feas.max() - e_feas.min())),
            p_opt=float(probs[_index(lc.exact)]), uniform_p_opt=1 / len(sets),
            feasible=float(probs[feas_idx].sum()),
            depth=int(run["depth"]), gates=int(run["gates"]), evaluations=int(run["evaluations"]),
            exact_optimum=exact_sites, top_counts=scored,
            final=dict(sites=final["sites"], objective=final["objective"], rank=final["rank"]),
            quantum_agreed=final["sites"] == exact_sites,
            objective=run.get("objective", "mean"), warm_start=False)
