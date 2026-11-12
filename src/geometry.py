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
    design_mag: np.ndarray | None = None  # (E,) magnitudes of `design`, when known (optional)
    valid_mag: np.ndarray | None = None   # (V,) magnitudes of `valid`, when known (optional)

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


def _rows(events: np.ndarray, sites: np.ndarray, v: float = V_P) -> np.ndarray:
    """Sensitivity rows g[e, s] = d(arrival time)/d(x, y, z, origin time), shape (E, S, 4)."""
    diff = events[:, None, :] - np.column_stack([sites, np.zeros(len(sites))])[None]
    dist = np.linalg.norm(diff, axis=2, keepdims=True)
    return np.concatenate([diff / (v * dist), np.ones_like(dist)], axis=2)


# ----------------------------------------------------------------------- hearing range (opt-in)
#
# A far station cannot hear a small aftershock, and a weak arrival is picked less precisely.
# This follows the idea of NetOpt3D (Hardt & Scherbaum 1994), where the picking error depends on
# the signal-to-noise ratio, and Aki (1976) on signal-to-noise in seismic measurements. It is a
# SIMPLIFICATION: one attenuation law, one noise level for every site, no site effects, no
# frequency dependence and no instrument response. The constants below are assumptions, not
# measurements, and are stated in the report.
#
#   amplitude:  Wood-Anderson-equivalent peak amplitude from the southern-California local
#               magnitude law of Hutton & Boore (1987):
#                   log10 A[mm] = M - 1.110 log10(r / 100) - 0.00189 (r - 100) - 3.0
#               (r = hypocentral distance in km; by definition M 3 at 100 km gives 1 mm).
#   P wave:     the first-arriving P wave is taken as P_TO_PEAK of that (S-dominated) peak.
#   noise:      one assumed rural background level, NOISE_WA_MM (Wood-Anderson-equivalent).
#   SNR < 5:    the station does not count for that event (no pick).
#   pick error: sigma = SIGMA_T * max(1, SNR_GOOD / SNR), so 0.1 s at SNR >= 10, 0.2 s at SNR 5.
#   With these numbers an M 2.5 is heard to about 55 km and an M 3.0 to about 150 km.
NOISE_WA_MM = 0.03       # assumed quiet rural background noise, mm (Wood-Anderson equivalent)
P_TO_PEAK = 0.2          # assumed P amplitude as a fraction of the Wood-Anderson peak
MIN_SNR = 5.0            # below this the arrival is not picked (decision 16)
SNR_GOOD = 10.0          # at or above this the pick error is the base SIGMA_T
MIN_DIST_KM = 1.0        # distances are clipped here so the law stays finite
# With hearing range a small event may be heard by fewer than 4 stations, which leaves its location
# undetermined. A weak prior (50 km in each coordinate, 10 s in origin time) keeps the information
# matrix invertible; it is used only when hearing=True.
PRIOR_KM, PRIOR_S = 50.0, 10.0


def wa_amplitude_mm(mag, r_km):
    """Wood-Anderson-equivalent peak amplitude in mm (Hutton & Boore 1987 attenuation)."""
    r = np.maximum(np.asarray(r_km, float), MIN_DIST_KM)
    return 10.0 ** (np.asarray(mag, float) - 1.110 * np.log10(r / 100.0) - 0.00189 * (r - 100.0) - 3.0)


def snr(mag, r_km):
    """Assumed P-wave signal-to-noise ratio of an event of magnitude `mag` at hypocentral distance r_km."""
    return P_TO_PEAK * wa_amplitude_mm(mag, r_km) / NOISE_WA_MM


def pick_sigma(snr_value):
    """Arrival-time picking error in s for a signal-to-noise ratio; inf when the event is not heard."""
    q = np.asarray(snr_value, float)
    with np.errstate(divide="ignore"):
        sigma = SIGMA_T * np.maximum(1.0, SNR_GOOD / q)
    return np.where(q >= MIN_SNR, sigma, np.inf)


def event_magnitudes(inst: "Instance", events: np.ndarray, mags=None) -> np.ndarray:
    """Magnitudes for `events`: `mags` if given, else column 3 of an (E, >=4) array, else the
    instance's design_mag / valid_mag when `events` is inst.design / inst.valid."""
    if mags is not None:
        out = np.asarray(mags, float).reshape(-1)
    elif np.ndim(events) == 2 and np.shape(events)[1] >= 4:
        out = np.asarray(events, float)[:, 3]
    elif events is inst.design and inst.design_mag is not None:
        out = np.asarray(inst.design_mag, float)
    elif events is inst.valid and inst.valid_mag is not None:
        out = np.asarray(inst.valid_mag, float)
    else:
        raise ValueError("hearing=True needs magnitudes: pass mags=, an (E, 5) event array, "
                         "or an Instance with design_mag / valid_mag")
    if len(out) != len(events):
        raise ValueError(f"{len(out)} magnitudes for {len(events)} events")
    return out


def pick_weights(xyz: np.ndarray, sites: np.ndarray, mags: np.ndarray) -> np.ndarray:
    """1 / sigma^2 for every event and site, shape (E, S); 0 where the site cannot hear the event."""
    sites3 = np.column_stack([sites, np.zeros(len(sites))])
    r = np.linalg.norm(xyz[:, None, :] - sites3[None], axis=2)
    return 1.0 / pick_sigma(snr(mags[:, None], r)) ** 2


class Scorer:
    """Location-quality scores of a network = permanent stations + chosen candidates.

    Optional, off by default (the defaults reproduce the published proof of concept exactly):
      * hearing=True: per station-event pick error from signal-to-noise (see the constants above);
        a pair with signal-to-noise under 5 does not count. Needs magnitudes (`mags`, an (E, 5)
        event array, or the instance's design_mag / valid_mag).
      * velocities=[...], weights=[...]: an ensemble of uniform P velocities (km/s); the D-score
        and the blur are the weighted means over the models (weights default to equal).
        `fisher`, `base` and `add` refer to the first model.
    """

    def __init__(self, inst: Instance, events: np.ndarray, *, mags=None, hearing: bool = False,
                 velocities=None, weights=None):
        if not hearing and velocities is None:
            events = np.asarray(events, float)[:, :3]
            gp = _rows(events, inst.stations)
            self.base = np.einsum("esi,esj->eij", gp, gp) / SIGMA_T**2   # Fisher info, permanent net
            gc = _rows(events, inst.candidates)
            self.add = np.einsum("esi,esj->esij", gc, gc) / SIGMA_T**2   # rank-1 term per candidate
            self.velocities, self.model_weights = (V_P,), (1.0,)
            self._models = [(self.base, self.add)]
            return

        xyz = np.asarray(events, float)[:, :3]
        vel = tuple(float(v) for v in (velocities if velocities is not None else (V_P,)))
        w = np.full(len(vel), 1.0 / max(len(vel), 1)) if weights is None else np.asarray(weights, float).reshape(-1)
        if not vel or len(w) != len(vel) or np.any(w < 0) or w.sum() <= 0 or min(vel) <= 0:
            raise ValueError("velocities must be positive; weights non-negative, one per velocity, not all zero")
        self.velocities, self.model_weights = vel, tuple(float(x) for x in w / w.sum())
        if hearing:
            m = event_magnitudes(inst, events, mags)
            wp, wc = pick_weights(xyz, inst.stations, m), pick_weights(xyz, inst.candidates, m)
            prior = np.diag([PRIOR_KM**-2] * 3 + [PRIOR_S**-2])
        else:
            wp = np.full((len(xyz), len(inst.stations)), SIGMA_T**-2)
            wc = np.full((len(xyz), len(inst.candidates)), SIGMA_T**-2)
            prior = np.zeros((4, 4))
        self._models = []
        for v in vel:
            gp, gc = _rows(xyz, inst.stations, v), _rows(xyz, inst.candidates, v)
            base = np.einsum("es,esi,esj->eij", wp, gp, gp) + prior
            add = np.einsum("es,esi,esj->esij", wc, gc, gc)
            self._models.append((base, add))
        self.base, self.add = self._models[0]

    @staticmethod
    def _fisher(model, selected) -> np.ndarray:
        base, add = model
        sel = list(selected)
        return base + add[:, sel].sum(axis=1) if sel else base

    def fisher(self, selected) -> np.ndarray:
        sel = list(selected)
        return self.base + self.add[:, sel].sum(axis=1) if sel else self.base

    def d_score(self, selected) -> float:
        """D-optimality: sum over events of log det of the location Fisher matrix (higher is better)."""
        if len(self._models) == 1:
            return float(np.linalg.slogdet(self.fisher(selected))[1].sum())
        return float(sum(w * np.linalg.slogdet(self._fisher(m, selected))[1].sum()
                         for w, m in zip(self.model_weights, self._models)))

    def blur_km(self, selected) -> float:
        """Mean expected hypocentre uncertainty in km: sqrt(trace of the x,y,z covariance)."""
        if len(self._models) == 1:
            cov = np.linalg.inv(self.fisher(selected))
            return float(np.sqrt(np.trace(cov[:, :3, :3], axis1=1, axis2=2)).mean())
        out = 0.0
        for w, m in zip(self.model_weights, self._models):
            cov = np.linalg.inv(self._fisher(m, selected))
            out += w * float(np.sqrt(np.trace(cov[:, :3, :3], axis1=1, axis2=2)).mean())
        return out
