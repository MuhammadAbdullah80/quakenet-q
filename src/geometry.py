"""Problem instance and the "true" seismological score.

Everything here is classical. It turns the cached USGS/IRIS data into:
  * a design set of aftershocks (what responders know at decision time),
  * a validation set of later aftershocks (what the network must then record),
  * candidate sites for portable seismometers and an access-risk cost per site,
  * the D-optimal score of a network (Rabinowitz & Steinberg 1990) and a
    plain-language "blur" metric: the expected location uncertainty in km.

Physics model (deliberately simple, stated as a limitation in the report):
P-wave travel time t = |h - r| / v through a uniform half-space, v = 6 km/s.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

V_P = 6.0            # km/s, uniform crustal P velocity
SIGMA_T = 0.1        # s, assumed arrival-time picking error
DECISION_HOURS = 12  # responders plan with the aftershocks seen in the first 12 h
KM_PER_DEG = 111.19
LAT0, LON0 = 35.75, -117.55  # centre of the study box

N_CANDIDATES = 10
K_SENSORS = 4
GRID_N = 6               # candidate grid is GRID_N x GRID_N over the study box
MIN_STATION_GAP_KM = 6.0  # a candidate must not duplicate a permanent station
RISK_LENGTH_KM = 5.0      # access risk decays with distance from the active rupture
BOX = (35.4, 36.1, -117.9, -117.2)


def to_km(lat, lon) -> np.ndarray:
    """Equirectangular projection to local km (x east, y north)."""
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    x = (lon - LON0) * np.cos(np.radians(LAT0)) * KM_PER_DEG
    y = (lat - LAT0) * KM_PER_DEG
    return np.stack([x, y], axis=-1)


@dataclass(frozen=True)
class Instance:
    design: np.ndarray      # (E, 3) x, y, depth in km: aftershocks known at decision time
    valid: np.ndarray       # (V, 3) later aftershocks, used only for evaluation
    stations: np.ndarray    # (M, 2) permanent stations
    station_names: tuple
    candidates: np.ndarray  # (N, 2) candidate sites for portable sensors
    risk: np.ndarray        # (N,) access-risk cost in [0, 1]
    mainshock: np.ndarray   # (3,)
    k: int = K_SENSORS

    @property
    def n(self) -> int:
        return len(self.candidates)

    def feasible_sets(self) -> list[tuple[int, ...]]:
        return list(combinations(range(self.n), self.k))


def load_instance() -> Instance:
    ev = json.loads((DATA_DIR / "events.json").read_text())["events"]
    st = json.loads((DATA_DIR / "stations.json").read_text())["stations"]

    main = max(ev, key=lambda e: e["mag"])
    t0 = main["time_ms"]
    cut = t0 + DECISION_HOURS * 3600e3

    def xyz(rows):
        xy = to_km([e["lat"] for e in rows], [e["lon"] for e in rows])
        z = np.clip([e["depth_km"] for e in rows], 0.5, None)  # avoid zero/negative depths
        return np.column_stack([xy, z])

    design = xyz([e for e in ev if t0 < e["time_ms"] <= cut])
    valid = xyz([e for e in ev if e["time_ms"] > cut])
    stations = to_km([s["lat"] for s in st], [s["lon"] for s in st])

    # Candidate rule: regular grid over the study box; drop nodes that sit next
    # to a permanent station; keep the N nodes closest to the centre of the
    # early aftershock cloud (a sensor 40 km away adds little).
    lats = np.linspace(BOX[0], BOX[1], GRID_N + 2)[1:-1]
    lons = np.linspace(BOX[2], BOX[3], GRID_N + 2)[1:-1]
    grid = to_km(*np.meshgrid(lats, lons, indexing="ij")).reshape(-1, 2)
    gap = np.linalg.norm(grid[:, None] - stations[None], axis=2).min(axis=1)
    grid = grid[gap >= MIN_STATION_GAP_KM]
    centre = design[:, :2].mean(axis=0)
    order = np.argsort(np.linalg.norm(grid - centre, axis=1))[:N_CANDIDATES]
    cand = grid[np.sort(order)]

    # Access-risk rule: sites close to the active rupture are the most valuable
    # scientifically but the riskiest and slowest to reach (surface rupture,
    # damaged roads, restricted land). risk = exp(-d / 5 km), d = distance to
    # the nearest early aftershock epicentre.
    d = np.linalg.norm(cand[:, None] - design[None, :, :2], axis=2).min(axis=1)
    risk = np.exp(-d / RISK_LENGTH_KM)

    return Instance(design, valid, stations, tuple(s["sta"] for s in st), cand, risk,
                    xyz([main])[0])


def _rows(events: np.ndarray, sites: np.ndarray) -> np.ndarray:
    """Sensitivity rows g[e, s] = d(arrival time)/d(x, y, z, origin time), shape (E, S, 4)."""
    diff = events[:, None, :] - np.column_stack([sites, np.zeros(len(sites))])[None]
    dist = np.linalg.norm(diff, axis=2, keepdims=True)
    return np.concatenate([diff / (V_P * dist), np.ones_like(dist)], axis=2)


class Scorer:
    """Location-quality scores of a network = permanent stations + chosen candidates."""

    def __init__(self, inst: Instance, events: np.ndarray):
        gp = _rows(events, inst.stations)
        self.base = np.einsum("esi,esj->eij", gp, gp) / SIGMA_T**2   # Fisher info, permanent net
        gc = _rows(events, inst.candidates)
        self.add = np.einsum("esi,esj->esij", gc, gc) / SIGMA_T**2   # rank-1 term per candidate

    def fisher(self, selected) -> np.ndarray:
        sel = list(selected)
        return self.base + self.add[:, sel].sum(axis=1) if sel else self.base

    def d_score(self, selected) -> float:
        """D-optimality: sum over events of log det of the location Fisher matrix (higher is better)."""
        return float(np.linalg.slogdet(self.fisher(selected))[1].sum())

    def blur_km(self, selected) -> float:
        """Mean expected hypocentre uncertainty in km: sqrt(trace of the x,y,z covariance)."""
        cov = np.linalg.inv(self.fisher(selected))
        return float(np.sqrt(np.trace(cov[:, :3, :3], axis1=1, axis2=2)).mean())
