"""Small fakes with the signatures of the science layer (docs/API.md, "Internal interfaces"), so the
agent and the v2 API are tested on their own. No test functions live here."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from src.agent.toolkit import Toolkit
from src.baselines import expert_rule
from src.geometry import Instance

SIGMA = 0.1
POISON = (900.0, 900.0)       # an aftershock after every replay window; no step may ever see it


@dataclass(frozen=True)
class FakeEventData:
    event_id: str
    usgs_id: str
    name: str
    magnitude: float
    time_utc: datetime
    lat: float
    lon: float
    depth_km: float
    lat0: float
    lon0: float
    aftershocks: np.ndarray
    stations: np.ndarray
    station_names: tuple
    pool: np.ndarray
    feasibility_checked: bool
    radius_km: float

    def to_latlon(self, x_km, y_km):
        lat = self.lat0 + y_km / 111.19
        lon = self.lon0 + x_km / (111.19 * math.cos(math.radians(self.lat0)))
        return float(lat), float(lon)


def make_event(event_id="fakequake", usgs_id="xx0001", hours_old: float = 24 * 400, n_stations=4) -> FakeEventData:
    """Aftershocks near (0, 0) for the first 12 hours, then a cluster 12 km east (a drift), and one
    poison event at hour 200."""
    rng = np.random.default_rng(1)
    early = np.column_stack([rng.normal(0, 1.5, 40), rng.normal(0, 1.5, 40), rng.uniform(4, 10, 40),
                             rng.uniform(2.5, 4.5, 40), np.sort(rng.uniform(0.1, 11.9, 40))])
    late = np.column_stack([rng.normal(12, 1.0, 40), rng.normal(0, 1.0, 40), rng.uniform(4, 10, 40),
                            rng.uniform(2.5, 4.5, 40), np.sort(rng.uniform(12.1, 23.9, 40))])
    poison = np.array([[POISON[0], POISON[1], 8.0, 3.0, 200.0]])
    angles = np.linspace(0, 2 * np.pi, n_stations, endpoint=False) + 0.3
    stations = np.column_stack([30 * np.cos(angles), 30 * np.sin(angles)])
    return FakeEventData(event_id=event_id, usgs_id=usgs_id, name="Fake quake", magnitude=6.8,
                         time_utc=datetime.now(timezone.utc) - timedelta(hours=hours_old),
                         lat=35.0, lon=-117.0, depth_km=8.0, lat0=35.0, lon0=-117.0,
                         aftershocks=np.vstack([early, late, poison]), stations=stations,
                         station_names=tuple(f"S{i}" for i in range(n_stations)), pool=np.zeros((0, 2)),
                         feasibility_checked=True, radius_km=60.0)


CANDIDATES = np.array([[8, 0], [0, 8], [-8, 0], [0, -8], [5.7, 5.7], [-5.7, -5.7], [16, 3], [16, -3], [20, 0],
                       [-5.7, 5.7]], float)


class FakeScorer:
    """Same signature as src.geometry.Scorer; uniform-velocity D-criterion; records what it saw."""
    seen: list = []

    def __init__(self, inst, events, *, mags=None, hearing=False, velocities=None, weights=None):
        ev = np.asarray(events, float)[:, :3]
        FakeScorer.seen.append(ev.copy())
        v = float((velocities or (6.0,))[0])

        def rows(sites):
            diff = ev[:, None, :] - np.column_stack([sites, np.zeros(len(sites))])[None]
            dist = np.linalg.norm(diff, axis=2, keepdims=True)
            return np.concatenate([diff / (v * dist), np.ones_like(dist)], axis=2)
        gp, gc = rows(inst.stations), rows(inst.candidates)
        self.base = np.einsum("esi,esj->eij", gp, gp) / SIGMA**2 + np.eye(4) * 1e-3
        self.add = np.einsum("esi,esj->esij", gc, gc) / SIGMA**2

    def d_score(self, selected) -> float:
        sel = list(selected)
        f = self.base + self.add[:, sel].sum(axis=1) if sel else self.base
        return float(np.linalg.slogdet(f)[1].sum())


class Calls:
    def __init__(self):
        self.planning_hours: list[float] = []
        self.solver: list[dict] = []


def fake_solver_factory(calls: Calls, mode: str = "good"):
    """Returns the exact best k-site network ("good") or always the second best ("bad")."""
    def solver(h, k, reps, seed=0, restarts=4, shots=1024, init=None, maxiter=250, cvar_alpha=None, diag=None):
        calls.solver.append(dict(reps=reps, shots=shots, init=init, restarts=restarts, cvar_alpha=cvar_alpha,
                                 has_diag=diag is not None))
        n = h.num_qubits
        idx = np.arange(2 ** n)
        weight = ((idx[:, None] >> np.arange(n)) & 1).sum(axis=1)
        order = [int(i) for i in np.argsort(diag) if weight[i] == k]
        pick = order[0] if mode == "good" else order[1]
        sel = tuple(i for i in range(n) if pick >> i & 1)
        return dict(theta=[0.1 * (j + 1) for j in range(2 * reps)], energy=0.0, counts={sel: shots},
                    evaluations=3, depth=5, gates=9, objective="cvar" if cvar_alpha else "mean")
    return solver


def make_toolkit(calls: Calls | None = None, mode: str = "good", events: dict | None = None,
                 usgs: dict | None = None) -> Toolkit:
    calls = calls or Calls()
    events = events if events is not None else {"fakequake": make_event()}
    usgs = usgs if usgs is not None else {}

    def load_event_data(event_id):
        return events[event_id]

    def event_from_usgs(usgs_id, *, station_radius_km=100.0):
        value = usgs[usgs_id]
        if isinstance(value, Exception):
            raise value
        events[value.event_id] = value
        return value

    def list_events():
        return [dict(id=e.event_id, usgs_id=e.usgs_id, name=e.name, magnitude=e.magnitude,
                     time_utc=e.time_utc.isoformat(), lat=e.lat, lon=e.lon,
                     kind="live" if e.usgs_id in usgs else "benchmark", cached=True) for e in events.values()]

    def planning_events(data, at_hours, *, min_real=30, seed=0):
        calls.planning_hours.append(float(at_hours))
        real = data.aftershocks[data.aftershocks[:, 4] <= at_hours]
        if len(real) >= min_real:
            return np.array(real), False
        rng = np.random.default_rng(seed)
        m = 30 - len(real)
        synth = np.column_stack([rng.normal(0, 2, m), rng.normal(0, 2, m), np.full(m, 8.0), np.full(m, 3.0),
                                 np.zeros(m)])
        return np.vstack([synth, real]), True

    def select_sites(data, events, *, n=10, min_spacing_km=4.0):
        cand = CANDIDATES[:n]
        return cand.copy(), [[data.to_latlon(x + 1, y)] for x, y in cand]

    def make_instance(data, candidates, events, *, k=4, valid=None):
        ev = np.asarray(events, float)
        cand = np.asarray(candidates, float)
        d = np.linalg.norm(cand[:, None] - ev[None, :, :2], axis=2).min(axis=1)
        valid = np.zeros((0, 3)) if valid is None else np.asarray(valid, float)[:, :3]
        return Instance(ev[:, :3].copy(), valid, np.asarray(data.stations, float), tuple(data.station_names), cand,
                        np.exp(-d / 5.0), np.array([0.0, 0.0, data.depth_km]), k=k)

    def location_errors(inst, selected, events, trials=1, seed=0):
        return np.full(len(events) * trials, 3.0 / (1 + len(selected)))

    return Toolkit(load_event_data=load_event_data, event_from_usgs=event_from_usgs, list_events=list_events,
                   planning_events=planning_events, select_sites=select_sites, make_instance=make_instance,
                   scorer=FakeScorer, solver=fake_solver_factory(calls, mode), location_errors=location_errors,
                   expert_rule=expert_rule)


class QuakeNetErrorLike(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def feed_body(quakes) -> bytes:
    """A USGS GeoJSON summary feed with the given (id, magnitude, hours_ago, lat, lon) rows."""
    import json
    import time
    now_ms = time.time() * 1000
    features = [dict(type="Feature", id=uid, properties=dict(mag=mag, place=f"Near {uid}",
                                                              time=int(now_ms - ago * 3600e3)),
                     geometry=dict(type="Point", coordinates=[lon, lat, 10.0]))
                for uid, mag, ago, lat, lon in quakes]
    return json.dumps(dict(type="FeatureCollection", features=features)).encode()
