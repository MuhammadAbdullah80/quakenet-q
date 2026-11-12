"""The quantum part: constraint-preserving QAOA written directly in Qiskit.

Circuit (p layers):
    |Dicke(n, k)>  --[ cost layer: exp(-i gamma H) ]--[ XY ring mixer(beta) ]-- x p --> measure

* The Dicke state is the equal superposition of every bitstring with exactly k
  ones, i.e. every allowed network. We build it with the deterministic circuit of
  Bartschi & Eidenbenz (2019), implemented here from the paper's description.
* The XY mixer swaps a 1 and a 0 between neighbouring qubits, so the number of
  chosen sites never changes (Hadfield et al. 2019). No penalty weight is needed.
* A classical optimiser (COBYLA) tunes the 2p angles using the Estimator primitive;
  the Sampler primitive then draws candidate networks.

`run_penalty_qaoa` is the textbook alternative (|+> start, X mixer, quadratic
penalty) used as an ablation.
"""
from __future__ import annotations

from math import acos, comb, sqrt

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector
from qiskit.circuit.library import RYGate, XXPlusYYGate
from qiskit.primitives import StatevectorEstimator, StatevectorSampler
from qiskit.quantum_info import Operator, SparsePauliOp, Statevector
from scipy.optimize import minimize


# --------------------------------------------------------------------------- circuits
def dicke_state(n: int, k: int) -> QuantumCircuit:
    """Deterministic Dicke-state preparation (Bartschi & Eidenbenz, FCT 2019)."""
    qc = QuantumCircuit(n, name=f"Dicke({n},{k})")
    qc.x(range(n - k, n))                      # input |0..0 1..1> with k ones
    for m in range(n, 1, -1):                  # split-and-cyclic-shift blocks on the first m qubits
        last = m - 1
        for l in range(1, min(k, m - 1) + 1):
            tgt = last - l
            theta = 2 * acos(sqrt(l / m))
            qc.cx(tgt, last)
            if l == 1:
                qc.cry(theta, last, tgt)
            else:
                qc.append(RYGate(theta).control(2, annotated=False), [last, tgt + 1, tgt])
            qc.cx(tgt, last)
    return qc


def cost_layer(qc: QuantumCircuit, h: SparsePauliOp, gamma) -> None:
    """exp(-i gamma H) for a Hamiltonian made of products of Z (Z, ZZ, ZZZ, ...).

    A product of Z on several qubits is the parity of those qubits, so we compute the parity
    onto the last qubit with a CX ladder, rotate it, and undo the ladder.
    """
    for label, qubits, coeff in h.to_sparse_list():
        c, q = float(np.real(coeff)), list(qubits)
        if set(label) != {"Z"}:
            raise ValueError(f"cost Hamiltonian must be diagonal, got term {label}")
        if len(q) == 1:
            qc.rz(2 * gamma * c, q[0])
        elif len(q) == 2:
            qc.rzz(2 * gamma * c, q[0], q[1])
        else:
            ladder = list(zip(q, q[1:]))
            for a, b in ladder:
                qc.cx(a, b)
            qc.rz(2 * gamma * c, q[-1])
            for a, b in reversed(ladder):
                qc.cx(a, b)


def xy_ring_mixer(qc: QuantumCircuit, beta) -> None:
    """Parity-ordered ring of exp(-i beta (XX+YY)/2) gates; conserves the number of ones."""
    n = qc.num_qubits
    pairs = [(i, (i + 1) % n) for i in range(n)]
    for i, j in pairs[0::2] + pairs[1::2]:
        qc.append(XXPlusYYGate(2 * beta), [i, j])


def xy_qaoa_circuit(h: SparsePauliOp, k: int, reps: int) -> QuantumCircuit:
    n = h.num_qubits
    gam, bet = ParameterVector("gamma", reps), ParameterVector("beta", reps)
    qc = QuantumCircuit(n)
    qc.compose(dicke_state(n, k), inplace=True)
    for layer in range(reps):
        cost_layer(qc, h, gam[layer])
        xy_ring_mixer(qc, bet[layer])
    return qc


def penalty_qaoa_circuit(h: SparsePauliOp, reps: int) -> QuantumCircuit:
    n = h.num_qubits
    gam, bet = ParameterVector("gamma", reps), ParameterVector("beta", reps)
    qc = QuantumCircuit(n)
    qc.h(range(n))
    for layer in range(reps):
        cost_layer(qc, h, gam[layer])
        qc.rx(2 * bet[layer], range(n))
    return qc


# --------------------------------------------------------------------------- CVaR objective
def diagonal(h: SparsePauliOp) -> np.ndarray:
    """Diagonal of a Hamiltonian made only of Z products, indexed like a Qiskit statevector."""
    n = h.num_qubits
    idx = np.arange(2**n)
    bits = (idx[:, None] >> np.arange(n)) & 1
    out = np.zeros(2**n)
    for label, qubits, coeff in h.to_sparse_list():
        if set(label) - {"Z"}:
            raise ValueError(f"Hamiltonian must be diagonal, got term {label}")
        parity = bits[:, list(qubits)].sum(axis=1) % 2 if len(qubits) else np.zeros(2**n, int)
        out += float(np.real(coeff)) * (1 - 2 * parity)
    return out


def cvar_value(probs: np.ndarray, diag: np.ndarray, alpha: float) -> float:
    """Conditional value at risk: the mean energy of the best (lowest) alpha fraction of the
    outcome distribution (Barkoutsos et al. 2020). Computed exactly from the probabilities."""
    order = np.argsort(diag, kind="stable")
    p, e = np.asarray(probs, float)[order], np.asarray(diag, float)[order]
    before = np.concatenate([[0.0], np.cumsum(p)[:-1]])
    take = np.clip(alpha - before, 0.0, p)                  # probability mass taken from each state
    return float((take * e).sum() / alpha)


class XYQaoaSimulator:
    """Exact output distribution of xy_qaoa_circuit(h, k, reps) for given angles, computed directly.

    Same circuit, faster arithmetic: the Dicke state is computed once; the cost layer, a product
    of commuting Z rotations, is exp(-i gamma H) = multiplication by exp(-i gamma diag(H)) (equal
    to the gate sequence up to a global phase); each XY mixer gate is its 4x4 matrix applied to
    the state tensor in the circuit's order. Used by the CVaR objective, which needs the full
    distribution at every step. The tests check it against Statevector of the circuit.
    """

    def __init__(self, h: SparsePauliOp, k: int, reps: int):
        self.n, self.reps = h.num_qubits, reps
        self.diag_h = diagonal(h)
        self.psi0 = Statevector(dicke_state(self.n, k)).data.copy()
        ring = [(i, (i + 1) % self.n) for i in range(self.n)]
        self.pairs = ring[0::2] + ring[1::2]

    def _mix(self, state: np.ndarray, beta: float) -> np.ndarray:
        n = self.n
        m = Operator(XXPlusYYGate(2 * beta)).data.reshape(2, 2, 2, 2)   # out_q1, out_q0, in_q1, in_q0
        t = state.reshape([2] * n)
        for i, j in self.pairs:                                       # gate qargs (i, j): q0 = i, q1 = j
            axes = [n - 1 - j, n - 1 - i]
            t = np.moveaxis(np.tensordot(m, t, axes=([2, 3], axes)), [0, 1], axes)
        return t.reshape(-1)

    def statevector(self, theta) -> np.ndarray:
        theta = np.asarray(theta, float)
        beta, gamma = theta[:self.reps], theta[self.reps:]
        psi = self.psi0
        for layer in range(self.reps):
            psi = np.exp(-1j * gamma[layer] * self.diag_h) * psi
            psi = self._mix(psi, beta[layer])
        return psi

    def probabilities(self, theta) -> np.ndarray:
        return np.abs(self.statevector(theta)) ** 2


# --------------------------------------------------------------------------- hybrid loop
def _optimise(qc: QuantumCircuit, h: SparsePauliOp, reps: int, seed: int, restarts: int, init=None,
              maxiter: int = 250, cvar_alpha: float | None = None, diag: np.ndarray | None = None,
              k: int | None = None):
    """COBYLA on the Estimator expectation value (or on the exact CVaR when cvar_alpha is set),
    best of several starts (random, plus `init` if given)."""
    est = StatevectorEstimator()
    params = list(qc.parameters)  # sorted by name: beta[0..], gamma[0..]
    rng = np.random.default_rng(seed)
    trace: list[float] = []

    if cvar_alpha is None:
        def energy(theta):
            val = float(est.run([(qc, h, theta)]).result()[0].data.evs)
            trace.append(val)
            return val
    else:
        sim = XYQaoaSimulator(h, k, reps)

        def energy(theta):
            probs = sim.probabilities(theta)
            val = cvar_value(probs, diag, cvar_alpha)
            trace.append(val)
            return val

    best = None
    starts = [rng.uniform(-0.5, 0.5, size=len(params)) for _ in range(restarts)]
    if init is not None:
        starts.insert(0, np.asarray(init, float))
    if not starts:
        raise ValueError("no starting point: give restarts >= 1 or init")
    for x0 in starts:
        res = minimize(energy, x0, method="COBYLA", options=dict(maxiter=maxiter, rhobeg=0.3))
        if best is None or res.fun < best.fun:
            best = res
    return best.x, float(best.fun), trace


def _sample(qc: QuantumCircuit, theta, shots: int, seed: int) -> dict[tuple[int, ...], int]:
    """Measure the tuned circuit; return {chosen site indices: count}."""
    meas = qc.copy()
    meas.measure_all()
    counts = StatevectorSampler(seed=seed).run([(meas, theta)], shots=shots).result()[0].data.meas.get_counts()
    out: dict[tuple[int, ...], int] = {}
    for bits, c in counts.items():           # Qiskit bitstrings put qubit 0 on the right
        sel = tuple(i for i, b in enumerate(reversed(bits)) if b == "1")
        out[sel] = out.get(sel, 0) + c
    return out


def _run(qc, h, reps, seed, restarts, shots, init=None, maxiter=250, cvar_alpha=None, diag=None, k=None):
    theta, e, trace = _optimise(qc, h, reps, seed, restarts, init, maxiter, cvar_alpha, diag, k)
    probs = Statevector(qc.assign_parameters(theta)).probabilities()  # exact distribution, for analysis
    out = dict(theta=theta.tolist(), energy=e, trace=trace, probs=probs,
               counts=_sample(qc, theta, shots, seed), depth=qc.decompose(reps=3).depth(), gates=qc.decompose(reps=3).size(),
               evaluations=len(trace), objective="mean" if cvar_alpha is None else "cvar")
    if cvar_alpha is not None:
        # "energy" stays the expectation value <H> at the chosen angles, as in the mean mode;
        # the optimised CVaR is reported separately.
        out["cvar"], out["cvar_alpha"] = e, float(cvar_alpha)
        out["energy"] = float(StatevectorEstimator().run([(qc, h, theta)]).result()[0].data.evs)
    return out


def run_xy_qaoa(h: SparsePauliOp, k: int, reps: int, seed: int = 0, restarts: int = 4, shots: int = 1024, init=None,
                maxiter: int = 250, cvar_alpha: float | None = None, diag: np.ndarray | None = None):
    """`init` is an optional starting point (angles in circuit-parameter order: all beta, then all gamma):
    the warm start. With restarts=0 only `init` is used.

    cvar_alpha (for example 0.1): minimise the CVaR, the mean of the best alpha fraction of the
    outcome distribution, instead of the mean energy. `diag` is the classical energy of every basis
    state (for example `src.qubo.energies(obj)`); if omitted it is the diagonal of `h`. A constant
    offset between the two does not change the optimum. The result gains "cvar" and "cvar_alpha".
    """
    if cvar_alpha is not None:
        if not 0.0 < float(cvar_alpha) <= 1.0:
            raise ValueError("cvar_alpha must be in (0, 1]")
        diag = diagonal(h) if diag is None else np.asarray(diag, float)
        if diag.shape != (2**h.num_qubits,):
            raise ValueError(f"diag must have 2**n = {2**h.num_qubits} entries, got {diag.shape}")
    return _run(xy_qaoa_circuit(h, k, reps), h, reps, seed, restarts, shots, init, maxiter, cvar_alpha, diag, k)


def extend_angles(theta, reps: int) -> np.ndarray:
    """Starting point for reps+1 layers from the best angles for `reps` layers (repeat the last layer)."""
    theta = np.asarray(theta, float)
    beta, gamma = theta[:reps], theta[reps:]
    return np.concatenate([beta, beta[-1:], gamma, gamma[-1:]])


def run_penalty_qaoa(h_pen: SparsePauliOp, reps: int, seed: int = 0, restarts: int = 4, shots: int = 1024):
    return _run(penalty_qaoa_circuit(h_pen, reps), h_pen, reps, seed, restarts, shots)


def dicke_probabilities(n: int, k: int) -> np.ndarray:
    """Exact measurement distribution of the Dicke state (uniform over the C(n,k) allowed networks)."""
    idx = np.arange(2**n)
    weight = ((idx[:, None] >> np.arange(n)) & 1).sum(axis=1)
    return (weight == k) / comb(n, k)
