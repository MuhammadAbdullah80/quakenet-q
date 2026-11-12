"""Turn the siting problem into a QUBO and an Ising Hamiltonian.

The D-optimal score is a log-determinant, which is not quadratic in the yes/no
variables. We keep the first two orders of its inclusion-exclusion expansion:

    D(S) - D(empty)  ~  sum_i a_i x_i  +  sum_{i<j} b_ij x_i x_j

    a_i  = D({i}) - D(empty)                      information gained by site i alone
    b_ij = D({i,j}) - D({i}) - D({j}) + D(empty)  interaction (negative = redundant pair)

Objective to MAXIMISE, subject to exactly k sites being chosen:

    f(x) = sum_i (a_i - lam * c_i) x_i + sum_{i<j} b_ij x_i x_j

where c_i is the access-risk cost and lam sets how much information one unit
of risk is worth. The approximation is exact for networks of one or two sites;
`src/baselines.py` and the experiment measure how well it ranks 4-site networks.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from .geometry import Instance, Scorer


@dataclass(frozen=True)
class Qubo:
    lin: np.ndarray    # (n,)  a_i - lam * c_i
    quad: np.ndarray   # (n, n) upper-triangular b_ij
    scale: float       # f is divided by this so that QAOA angles are O(1)

    @property
    def n(self) -> int:
        return len(self.lin)

    def value(self, selected) -> float:
        """f(x) in original (unscaled) units for a set of chosen site indices."""
        x = np.zeros(self.n)
        x[list(selected)] = 1.0
        return float(self.lin @ x + x @ self.quad @ x)


def build_qubo(inst: Instance, scorer: Scorer, lam: float) -> Qubo:
    n = inst.n
    d0 = scorer.d_score([])
    single = np.array([scorer.d_score([i]) for i in range(n)])
    a = single - d0
    b = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            b[i, j] = scorer.d_score([i, j]) - single[i] - single[j] + d0
    lin = a - lam * inst.risk
    return Qubo(lin, b, scale=float(max(np.abs(lin).max(), np.abs(b).max())))


def to_hamiltonian(q: Qubo, penalty: float = 0.0, k: int = 0) -> tuple[SparsePauliOp, float]:
    """Ising Hamiltonian H and constant so that  <x|H|x> + const = -f(x)/scale (+ penalty term).

    Uses x_i = (1 - Z_i)/2. Minimising H maximises f. With penalty > 0 the term
    penalty * (sum_i x_i - k)^2 is added (in scaled units); this is only used by the
    penalty-based ablation, the main solver enforces the constraint in the circuit.
    """
    n = q.n
    lin = -q.lin / q.scale
    quad = -q.quad / q.scale
    if penalty:
        # P (sum x - k)^2 = P [ sum_i (1 - 2k) x_i + 2 sum_{i<j} x_i x_j + k^2 ]   (x_i^2 = x_i)
        lin = lin + penalty * (1 - 2 * k)
        quad = quad + 2 * penalty * np.triu(np.ones((n, n)), 1)
    const = penalty * k**2
    z = np.zeros(n)
    terms = []
    for i in range(n):
        const += lin[i] / 2
        z[i] -= lin[i] / 2
        for j in range(i + 1, n):
            if quad[i, j]:
                const += quad[i, j] / 4
                z[i] -= quad[i, j] / 4
                z[j] -= quad[i, j] / 4
                terms.append(("ZZ", [i, j], quad[i, j] / 4))
    terms += [("Z", [i], z[i]) for i in range(n)]
    return SparsePauliOp.from_sparse_list(terms, num_qubits=n).simplify(), float(const)


def energies(q: Qubo, penalty: float = 0.0, k: int = 0) -> np.ndarray:
    """Classical energy -f(x)/scale (+ penalty) of every basis state, indexed like a Qiskit statevector
    (bit i of the index = qubit i = site i)."""
    n = q.n
    idx = np.arange(2**n)
    x = ((idx[:, None] >> np.arange(n)) & 1).astype(float)
    e = -(x @ q.lin + np.einsum("si,ij,sj->s", x, q.quad, x)) / q.scale
    if penalty:
        e = e + penalty * (x.sum(axis=1) - k) ** 2
    return e
