"""One plan: choose k of the n candidate sites with QAOA, check it exactly, explain it.

Steps (spec FR-11 to FR-22, docs/API.md "Sequences"):
 1. Build the exact objective over the candidates (Moebius expansion with order = k), with a move
    cost for every sensor that changes site compared with the current plan.
 2. Turn it into a Hamiltonian; run Dicke-state + XY-mixer QAOA, optimising the CVaR of the energy
    distribution. The start angles come from memory (warm start), or from random restarts when
    memory has none for this size (cold start).
 3. Re-score the 10 most frequently measured networks with the objective and keep the best.
 4. Enumerate every network to find the exact optimum. If the quantum choice differs, retry with
    two more layers and 4096 shots, at most twice; then publish the exact optimum with
    quantum_agreed = false.
 5. Explain each chosen site, estimate the location error of the plan and of the expert rule,
    and store the optimised angles in memory.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from itertools import combinations

import numpy as np

from src.qubo import Objective, build_objective, energies, to_hamiltonian

from .memory import Memory
from .toolkit import Toolkit

log = logging.getLogger("quakenet.agent")

TOP_M = 10                 # most frequent sampled networks that are re-scored
Sites = tuple[int, ...]
# Velocity-model ensemble of spec FR-10: uniform P-wave speeds, weighted by memory (FR-28).
VELOCITY_MODELS = {"uniform 5.5 km/s": 5.5, "uniform 6.0 km/s": 6.0, "uniform 6.5 km/s": 6.5}


@dataclass(frozen=True)
class Budget:
    """Optimiser and estimate budgets. Smaller values make tests fast; defaults follow the spec."""
    restarts: int = 4          # random starts on a cold start (FR-16)
    maxiter: int = 250         # COBYLA steps per start
    cvar_alpha: float = 0.1    # FR-15
    retries: int = 2           # FR-20
    retry_layers: int = 2
    retry_shots: int = 4096
    loc_events: int = 100      # aftershocks used for the location-error estimates
    loc_trials: int = 1


@dataclass
class Plan:
    sites: Sites
    public: dict               # the "plan" object of a sequence step (docs/API.md)
    details: dict              # extra fields for GET /events/{id}/plan
    predicted_score: float     # information gain minus risk cost, on the planning events
    centroid: tuple[float, float]
    inst: object               # the Instance the plan was made on (kept to score it later)
    events: np.ndarray         # the planning aftershocks (E, 5)
    velocities: tuple[float, ...]
    weights: tuple[float, ...]


def _index(sel) -> int:
    return sum(1 << i for i in sel)


def moves_between(current: Sites | None, chosen: Sites) -> list[dict]:
    if not current:
        return []
    gone = sorted(set(current) - set(chosen))
    new = sorted(set(chosen) - set(current))
    return [{"from": int(a), "to": int(b)} for a, b in zip(gone, new)]


def with_move_cost(obj: Objective, current: Sites | None, move_cost: float, k: int) -> Objective:
    """Add -move_cost * (number of sensors that change site) to the expansion.

    For a network S of exactly k sites, moves(S) = k - |S n current|. The constant -move_cost * k
    equals the sum over i in S of -move_cost (because |S| = k), so the whole term is linear:
    every site gets -move_cost, and every current site gets +move_cost back. The expansion stays
    exact for every k-site network.
    """
    if not current or not move_cost:
        return obj
    terms = dict(obj.terms)
    for i in range(obj.n):
        terms[(i,)] = terms.get((i,), 0.0) - move_cost + (move_cost if i in current else 0.0)
    return Objective(terms, obj.n, obj.order, scale=float(max(abs(v) for v in terms.values())))


def _extend(theta, layers: int, extra: int) -> list[float]:
    """Start angles for `layers + extra` layers: repeat the last layer (all beta, then all gamma)."""
    theta = list(map(float, theta))
    beta, gamma = theta[:layers], theta[layers:]
    return beta + beta[-1:] * extra + gamma + gamma[-1:] * extra


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _subsample(events: np.ndarray, m: int) -> np.ndarray:
    if len(events) <= m:
        return events
    return events[np.linspace(0, len(events) - 1, m).round().astype(int)]


def make_plan(data, events: np.ndarray, candidates: np.ndarray, *, current: Sites | None, settings: dict,
              memory: Memory, toolkit: Toolkit, budget: Budget = Budget(), seed: int = 0) -> Plan:
    """`events` (E, 5) are the planning aftershocks; `candidates` (n, 2) km; `current` the sites in
    place (None for a first plan). `settings` are the values of src.agent.settings."""
    t0 = time.time()
    events = np.asarray(events, float)
    k, lam = int(settings["sensors"]), float(settings["risk_weight"])
    move_cost = float(settings["move_cost"]) if current else 0.0
    current = tuple(sorted(int(i) for i in current)) if current else None
    inst = toolkit.make_instance(data, candidates, events, k=k)
    n = inst.n
    if not 1 <= k < n:
        raise ValueError(f"cannot choose {k} of {n} sites")
    xyz = events[:, :3]
    velocities, weights = ensemble(memory)
    scorer = toolkit.scorer(inst, xyz, mags=events[:, 3], hearing=bool(settings["hearing_range"]),
                            velocities=velocities, weights=weights)

    # 1. the exact objective, and the same objective computed directly for every network
    base = build_objective(inst, scorer, lam, order=k)
    obj = with_move_cost(base, current, move_cost, k)
    risk = np.asarray(inst.risk, float)
    d_empty = scorer.d_score([])
    sets = list(combinations(range(n), k))

    def gain(sel) -> float:                         # information gain minus risk cost
        return scorer.d_score(list(sel)) - d_empty - lam * float(risk[list(sel)].sum())

    def f_true(sel) -> float:
        return gain(sel) - move_cost * len(moves_between(current, tuple(sel)))

    f_all = np.array([f_true(s) for s in sets])
    exact = sets[int(f_all.argmax())]

    def rank(value: float) -> int:
        return int((f_all > value + 1e-9).sum()) + 1

    # 2-4. QAOA with the self-check and retries
    h, _ = to_hamiltonian(obj)
    diag = energies(obj)
    layers, shots = int(settings["qaoa_layers"]), int(settings["shots"])
    init = memory.warm_start(n, k, layers)
    warm = init is not None
    retries, picked, run, evaluations = 0, None, None, 0
    for attempt in range(budget.retries + 1):
        restarts = 0 if init is not None else budget.restarts
        run = toolkit.solver(h, k, layers, seed=seed + attempt, restarts=restarts, shots=shots, init=init,
                             maxiter=budget.maxiter, cvar_alpha=budget.cvar_alpha, diag=diag)
        evaluations += int(run.get("evaluations", 0))
        try:
            memory.add_angles(n, k, layers, run["theta"])
        except (ValueError, KeyError, TypeError):
            log.warning("solver returned unusable angles; not stored")
        counts = run["counts"]
        top = [tuple(s) for s in sorted(counts, key=counts.get, reverse=True) if len(s) == k][:TOP_M]
        picked = max(top, key=f_true) if top else None
        if picked == exact:
            break
        if attempt == budget.retries:
            break
        retries += 1
        old_layers = layers
        layers, shots = layers + budget.retry_layers, budget.retry_shots
        init = memory.warm_start(n, k, layers) or _extend(run["theta"], old_layers, budget.retry_layers)
    agreed = picked == exact
    chosen = picked if agreed else exact
    probs = run.get("probs")
    if probs is not None:
        p_opt = float(np.asarray(probs)[_index(exact)])
    else:
        p_opt = float(run["counts"].get(exact, 0)) / max(1, shots)

    # 5. explanation and checks
    centroid = tuple(float(v) for v in xyz[:, :2].mean(axis=0))
    ranks = {i: r + 1 for r, i in enumerate(sorted(range(n), key=lambda i: -base.terms[(i,)]))}
    sites_detail = []
    d_chosen = scorer.d_score(list(chosen))
    for i in chosen:
        single = float(base.terms[(i,)])                       # gain of the site alone, minus its risk cost
        alone = scorer.d_score([i]) - d_empty                  # information of the site alone
        marginal = d_chosen - scorer.d_score([j for j in chosen if j != i])   # what it adds to the others
        overlap = min(1.0, max(0.0, 1.0 - marginal / alone)) if alone > 0 else 0.0
        nearest = float(np.linalg.norm(xyz[:, :2] - inst.candidates[i], axis=1).min())
        parts = ["Largest gain of any single site" if ranks[i] == 1
                 else f"Single-site gain ranks {_ordinal(ranks[i])} of the {n} candidates"]
        parts.append("little overlap with the other chosen sites" if overlap < 0.1
                     else f"about {round(100 * overlap)}% of what it records is also covered by the other chosen sites")
        if current and i in current:
            parts.append("already in place, so keeping it avoids a move")
        reason = "; ".join(parts) + f"; {nearest:.1f} km from the nearest aftershock."
        sites_detail.append(dict(id=int(i), single_gain=round(single, 1), risk=round(float(risk[i]), 4),
                                 reason=reason))

    loc_events = _subsample(xyz, budget.loc_events)
    expected = float(np.mean(toolkit.location_errors(inst, chosen, loc_events, trials=budget.loc_trials)))
    expert_sites = tuple(sorted(toolkit.expert_rule(inst.stations, inst.candidates, np.array(centroid), k)))
    expert = float(np.mean(toolkit.location_errors(inst, expert_sites, loc_events, trials=budget.loc_trials)))

    moves = moves_between(current, chosen)
    public = dict(sites=[int(i) for i in chosen], risk=[round(float(risk[i]), 4) for i in chosen],
                  objective=round(float(f_true(chosen)), 3), exact_rank=rank(f_true(chosen)),
                  quantum_agreed=bool(agreed), retries=retries, p_opt_per_shot=round(p_opt, 5), moves=moves,
                  expected_error_km=round(expected, 3), expert_rule_error_km=round(expert, 3),
                  seconds=round(time.time() - t0, 1))
    details = dict(sites=sites_detail, quantum_rank=rank(f_true(picked)) if picked else None,
                   layers=layers, shots=shots, evaluations=evaluations, warm_start=warm,
                   objective_kind=run.get("objective", "mean"), expert_rule_sites=list(expert_sites),
                   aftershocks_used=len(events), velocities=list(velocities), weights=list(weights))
    log.info("plan: sites=%s agreed=%s retries=%d layers=%d evaluations=%d p_opt=%.4f rank=%d seconds=%.1f",
             public["sites"], agreed, retries, layers, evaluations, p_opt, public["exact_rank"], public["seconds"])
    return Plan(sites=tuple(int(i) for i in chosen), public=public, details=details,
                predicted_score=float(gain(chosen)), centroid=centroid, inst=inst, events=events,
                velocities=velocities, weights=weights)


def ensemble(memory: Memory) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Velocities and weights of the ensemble, from memory (equal weights on first use)."""
    weights = {m["name"]: m["weight"] for m in memory.model_weights()}
    names = [n for n in VELOCITY_MODELS if n in weights] or list(VELOCITY_MODELS)
    w = [float(weights.get(n, 1.0)) for n in names]
    total = sum(w) or 1.0
    return tuple(VELOCITY_MODELS[n] for n in names), tuple(x / total for x in w)


def score(plan: Plan, events: np.ndarray, *, settings: dict, toolkit: Toolkit, reference_count: int,
          velocities=None, weights=None) -> float:
    """A plan's score on a set of aftershocks: information gain scaled to `reference_count`
    aftershocks (the number it was planned on), minus the same risk cost. Scaling puts a score on
    newly recorded aftershocks on the same footing as the prediction made on the planning set."""
    events = np.asarray(events, float)
    inst = plan.inst
    scorer = toolkit.scorer(inst, events[:, :3], mags=events[:, 3], hearing=bool(settings["hearing_range"]),
                            velocities=velocities or plan.velocities,
                            weights=weights or (plan.weights if velocities is None else None))
    sel = list(plan.sites)
    info = (scorer.d_score(sel) - scorer.d_score([])) * reference_count / len(events)
    return float(info - float(settings["risk_weight"]) * float(np.asarray(inst.risk)[sel].sum()))


def information_scale(plan: Plan, settings: dict) -> float:
    """The predicted information gain alone (the predicted score plus its risk cost). Predicted and
    realised scores carry the same risk cost, so their difference is a difference in information;
    dividing by this keeps relative errors meaningful when the net score is close to zero."""
    risk_cost = float(settings["risk_weight"]) * float(np.asarray(plan.inst.risk)[list(plan.sites)].sum())
    return abs(float(plan.predicted_score) + risk_cost)


def realised_score(plan: Plan, events: np.ndarray, *, settings: dict, toolkit: Toolkit,
                   reference_count: int) -> float:
    """The plan's score on newly recorded aftershocks, with the plan's own model ensemble."""
    return score(plan, events, settings=settings, toolkit=toolkit, reference_count=reference_count)


def model_errors(plan: Plan, realised_events: np.ndarray, *, settings: dict, toolkit: Toolkit) -> dict[str, float]:
    """For each velocity model alone: relative error between the plan's predicted score (on the
    planning aftershocks) and its realised score (on the recorded ones). There are no measured
    arrival times here, so this rates how well each model's score carried over, not which model
    is physically right."""
    out = {}
    n = len(plan.events)
    for name, v in VELOCITY_MODELS.items():
        pred = score(plan, plan.events, settings=settings, toolkit=toolkit, reference_count=n, velocities=(v,))
        real = score(plan, realised_events, settings=settings, toolkit=toolkit, reference_count=n, velocities=(v,))
        risk_cost = float(settings["risk_weight"]) * float(np.asarray(plan.inst.risk)[list(plan.sites)].sum())
        denom = abs(pred + risk_cost)
        out[name] = abs(real - pred) / denom if denom else 1.0
    return out
