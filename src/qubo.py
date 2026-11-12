"""Turn the siting problem into a binary objective and an Ising Hamiltonian.

The D-optimal score D(S) is a log-determinant, which is not quadratic in the yes/no
variables. We expand it exactly over subsets of sites (a Moebius / inclusion-exclusion
expansion):

    g(S) = D(S) - lam * sum_{i in S} c_i          (c_i = access risk of site i)
    g(S) - g(empty) = sum over non-empty T subset of S of m_T

    m_{i}     = g({i}) - g(empty)                          gain of site i alone
    m_{i,j}   = g({i,j}) - g({i}) - g({j}) + g(empty)      pair interaction (negative = redundant)
    m_T       = g(T) - sum of m_U over all proper subsets U of T

Keeping terms up to `order` sites gives the objective to MAXIMISE:

    f(x) = sum_{|T| <= order} m_T * prod_{i in T} x_i        subject to exactly k sites

* order = 2 is a QUBO (the pairwise approximation used in the first version).
* order = k is EXACT for every network of k sites: f(S) = g(S) - g(empty). With k = 4 and
  10 sites this needs 385 terms, and the Hamiltonian then contains Z, ZZ, ZZZ and ZZZZ terms.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from .geometry import Instance, Scorer

Subset = tuple[int, ...]


@dataclass(frozen=True)
class Objective:
    terms: dict[Subset, float]   # m_T for every subset T with 1 <= |T| <= order
    n: int
    order: int
    scale: float                 # f is divided by this so that QAOA angles are O(1)

    def value(self, selected) -> float:
        """f(x) in original (unscaled) units for a set of chosen site indices."""
        sel = sorted(selected)
        return float(sum(self.terms[t] for r in range(1, min(self.order, len(sel)) + 1)
                         for t in combinations(sel, r)))


def build_objective(inst: Instance, scorer: Scorer, lam: float, order: int = 4) -> Objective:
    def g(subset: Subset) -> float:
        return scorer.d_score(subset) - lam * float(inst.risk[list(subset)].sum())

    moebius: dict[Subset, float] = {(): g(())}
    for r in range(1, order + 1):
        for t in combinations(range(inst.n), r):
            moebius[t] = g(t) - sum(moebius[u] for q in range(r) for u in combinations(t, q))
    del moebius[()]
    return Objective(moebius, inst.n, order, scale=float(max(abs(v) for v in moebius.values())))


def build_qubo(inst: Instance, scorer: Scorer, lam: float) -> Objective:
    """Pairwise (order-2) approximation: a true QUBO."""
    return build_objective(inst, scorer, lam, order=2)


def _scaled_terms(obj: Objective, penalty: float, k: int) -> tuple[dict[Subset, float], float]:
    """Terms of the function to MINIMISE, -f/scale (+ penalty), and its constant."""
    terms = {t: -m / obj.scale for t, m in obj.terms.items()}
    const = 0.0
    if penalty:
        # P (sum x - k)^2 = P [ sum_i (1 - 2k) x_i + 2 sum_{i<j} x_i x_j + k^2 ]   (x_i^2 = x_i)
        for i in range(obj.n):
            terms[(i,)] = terms.get((i,), 0.0) + penalty * (1 - 2 * k)
            for j in range(i + 1, obj.n):
                terms[(i, j)] = terms.get((i, j), 0.0) + 2 * penalty
        const = penalty * k**2
    return terms, const


def to_hamiltonian(obj: Objective, penalty: float = 0.0, k: int = 0) -> tuple[SparsePauliOp, float]:
    """Ising Hamiltonian H and constant so that  <x|H|x> + const = -f(x)/scale (+ penalty term).

    Uses x_i = (1 - Z_i)/2, so  prod_{i in T} x_i = 2^-|T| * sum_{U subset T} (-1)^|U| Z_U.
    Minimising H maximises f. The penalty term penalty * (sum_i x_i - k)^2 is only used by the
    penalty-based ablation; the main solver enforces the constraint in the circuit.
    """
    terms, const = _scaled_terms(obj, penalty, k)
    z: dict[Subset, float] = {}
    for t, c in terms.items():
        for r in range(len(t) + 1):
            for u in combinations(t, r):
                z[u] = z.get(u, 0.0) + c * (-1) ** r / 2 ** len(t)
    const += z.pop((), 0.0)
    ops = [("Z" * len(u), list(u), c) for u, c in z.items() if abs(c) > 1e-15]
    return SparsePauliOp.from_sparse_list(ops, num_qubits=obj.n), float(const)


def energies(obj: Objective, penalty: float = 0.0, k: int = 0) -> np.ndarray:
    """Classical energy -f(x)/scale (+ penalty) of every basis state, indexed like a Qiskit
    statevector (bit i of the index = qubit i = site i)."""
    terms, const = _scaled_terms(obj, penalty, k)
    idx = np.arange(2**obj.n)
    x = ((idx[:, None] >> np.arange(obj.n)) & 1).astype(float)
    e = np.full(len(idx), const)
    for t, c in terms.items():
        e += c * x[:, list(t)].prod(axis=1)
    return e
