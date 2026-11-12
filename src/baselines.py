"""Classical reference methods. Each returns a tuple of k chosen site indices.

`score` is any function mapping a set of site indices to a number to maximise
(e.g. the QUBO value, or the true D-score minus the risk cost).
"""
from __future__ import annotations

from itertools import combinations
from typing import Callable, Sequence

import numpy as np

Score = Callable[[Sequence[int]], float]


def brute_force(n: int, k: int, score: Score) -> tuple[int, ...]:
    """Exact optimum by enumerating every allowed network."""
    return max(combinations(range(n), k), key=score)


def greedy_forward(n: int, k: int, score: Score) -> tuple[int, ...]:
    """Add the single best site, k times."""
    chosen: list[int] = []
    for _ in range(k):
        chosen.append(max((i for i in range(n) if i not in chosen), key=lambda i: score(chosen + [i])))
    return tuple(sorted(chosen))


def backward_elimination(n: int, k: int, score: Score) -> tuple[int, ...]:
    """Start from all sites and drop the least useful one until k remain (as in Toledo et al. 2020)."""
    chosen = list(range(n))
    while len(chosen) > k:
        chosen.remove(max(chosen, key=lambda i: score([j for j in chosen if j != i])))
    return tuple(chosen)


def simulated_annealing(n: int, k: int, score: Score, seed: int = 0, steps: int = 300,
                        t_start: float = 1.0, t_end: float = 0.01) -> tuple[int, ...]:
    """Swap-move simulated annealing (the solver family used by Hardt & Scherbaum 1994)."""
    rng = np.random.default_rng(seed)
    cur = list(rng.choice(n, size=k, replace=False))
    cur_s = score(cur)
    best, best_s = list(cur), cur_s
    span = None
    for step in range(steps):
        t = t_start * (t_end / t_start) ** (step / (steps - 1))
        out = rng.integers(k)
        new = cur.copy()
        new[out] = rng.choice([i for i in range(n) if i not in cur])
        new_s = score(new)
        span = span or max(abs(new_s - cur_s), 1e-9)   # temperature unit = first observed score change
        if new_s >= cur_s or rng.random() < np.exp((new_s - cur_s) / (t * span)):
            cur, cur_s = new, new_s
            if cur_s > best_s:
                best, best_s = list(cur), cur_s
    return tuple(sorted(best))


def random_pick(n: int, k: int, seed: int = 0) -> tuple[int, ...]:
    return tuple(sorted(np.random.default_rng(seed).choice(n, size=k, replace=False).tolist()))
