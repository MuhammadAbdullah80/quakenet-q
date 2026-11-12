"""Independent checks of a network that do not rely on the planner's own score.

1. `location_errors`: a simulated location experiment. For each later aftershock we generate
   noisy P arrival times with a "true" wave speed that differs from the planner's, then actually
   locate the event with the planner's model (nonlinear least squares) and measure how far the
   answer is from the true position. This tests the nonlinear problem with a wrong velocity
   model, which the linearised D-criterion ignores.

2. `dn_score`: the D_N criterion of Coles & Curtis (2011), in the form given by Bloem, Curtis &
   Maurer (2020, eq. 26): ln det of the covariance of the predicted data across prior samples.
   A network scores highly when different earthquakes produce clearly different readings.
   Written from the published formula; no third-party code is used.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

from .geometry import SIGMA_T, V_P, Instance

V_TRUE = 5.8          # km/s: "real" wave speed in the experiment (planner assumes V_P = 6.0)
START_DEPTH = 8.0     # km: starting depth for every location


def _sites(inst: Instance, selected) -> np.ndarray:
    xy = np.vstack([inst.stations, inst.candidates[list(selected)]]) if len(selected) else inst.stations
    return np.column_stack([xy, np.zeros(len(xy))])


def location_errors(inst: Instance, selected, events: np.ndarray, trials: int = 3, seed: int = 0) -> np.ndarray:
    """3-D location error in km for each event and trial, shape (len(events) * trials,).

    The same noise is used for every network (it is drawn for all permanent and candidate
    sites, then sub-selected), so differences between networks are not due to luck.
    """
    rng = np.random.default_rng(seed)
    n_perm, n_cand = len(inst.stations), inst.n
    noise = rng.normal(0.0, SIGMA_T, size=(trials, len(events), n_perm + n_cand))
    cols = list(range(n_perm)) + [n_perm + i for i in selected]
    sites = _sites(inst, selected)

    errors = []
    for trial in range(trials):
        for e, hyp in enumerate(events):
            t_obs = np.linalg.norm(hyp - sites, axis=1) / V_TRUE + noise[trial, e, cols]
            first = sites[int(np.argmin(t_obs))]
            x0 = np.array([first[0], first[1], START_DEPTH, t_obs.min() - START_DEPTH / V_P])

            def residual(p):
                return (p[3] + np.linalg.norm(p[:3] - sites, axis=1) / V_P - t_obs) / SIGMA_T

            sol = least_squares(residual, x0, method="lm")
            errors.append(float(np.linalg.norm(sol.x[:3] - hyp)))
    return np.array(errors)


def dn_score(inst: Instance, selected, events: np.ndarray) -> float:
    """D_N criterion for networks of equal size (higher is better).

    Data are arrival times relative to the network mean, which removes the unknown origin
    time; one redundant component is dropped. The data-noise covariance is the same for all
    networks with the same number of stations, so it only shifts the score by a constant.
    """
    sites = _sites(inst, selected)
    t = np.linalg.norm(events[:, None, :] - sites[None], axis=2) / V_P     # (events, stations)
    d = (t - t.mean(axis=1, keepdims=True))[:, :-1]
    cov = np.cov(d, rowvar=False) / SIGMA_T**2
    return float(np.linalg.slogdet(cov)[1])
