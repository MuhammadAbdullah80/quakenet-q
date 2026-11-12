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
from qiskit.quantum_info import SparsePauliOp, Statevector
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
    """exp(-i gamma H) for a Hamiltonian made of Z and ZZ terms."""
    for label, qubits, coeff in h.to_sparse_list():
        c = float(np.real(coeff))
        if label == "Z":
            qc.rz(2 * gamma * c, qubits[0])
        elif label == "ZZ":
            qc.rzz(2 * gamma * c, qubits[0], qubits[1])


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


# --------------------------------------------------------------------------- hybrid loop
def _optimise(qc: QuantumCircuit, h: SparsePauliOp, reps: int, seed: int, restarts: int):
    """COBYLA on the Estimator expectation value, best of several random starts."""
    est = StatevectorEstimator()
    params = list(qc.parameters)  # sorted by name: beta[0..], gamma[0..]
    rng = np.random.default_rng(seed)
    trace: list[float] = []

    def energy(theta):
        val = float(est.run([(qc, h, theta)]).result()[0].data.evs)
        trace.append(val)
        return val

    best = None
    for _ in range(restarts):
        x0 = rng.uniform(-0.5, 0.5, size=len(params))
        res = minimize(energy, x0, method="COBYLA", options=dict(maxiter=250, rhobeg=0.3))
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


def _run(qc, h, reps, seed, restarts, shots):
    theta, e, trace = _optimise(qc, h, reps, seed, restarts)
    probs = Statevector(qc.assign_parameters(theta)).probabilities()  # exact distribution, for analysis
    return dict(theta=theta.tolist(), energy=e, trace=trace, probs=probs,
                counts=_sample(qc, theta, shots, seed), depth=qc.decompose(reps=3).depth(),
                evaluations=len(trace))


def run_xy_qaoa(h: SparsePauliOp, k: int, reps: int, seed: int = 0, restarts: int = 4, shots: int = 1024):
    return _run(xy_qaoa_circuit(h, k, reps), h, reps, seed, restarts, shots)


def run_penalty_qaoa(h_pen: SparsePauliOp, reps: int, seed: int = 0, restarts: int = 4, shots: int = 1024):
    return _run(penalty_qaoa_circuit(h_pen, reps), h_pen, reps, seed, restarts, shots)


def dicke_probabilities(n: int, k: int) -> np.ndarray:
    """Exact measurement distribution of the Dicke state (uniform over the C(n,k) allowed networks)."""
    idx = np.arange(2**n)
    weight = ((idx[:, None] >> np.arange(n)) & 1).sum(axis=1)
    return (weight == k) / comb(n, k)
