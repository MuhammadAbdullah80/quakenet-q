"""Simulated gate noise: how would the circuit fare on imperfect hardware? (a stand-in, not hardware)

The XY-mixer QAOA is run on a reduced Ridgecrest instance (the 6 candidates with the largest
single-site gain, choose 2) so that a noisy simulation is cheap. The angles are tuned without
noise; then the tuned circuit is run many times with random gate errors.

Noise model (an assumption, stated in the output):
  * the circuit is transpiled to the gate set rz, sx, x, cx (rz is "virtual" on most hardware
    and gets no error);
  * after every cx, with probability p (the "gate_error"), a random non-identity two-qubit Pauli
    (one of 15) hits its two qubits: a two-qubit depolarising channel;
  * after every sx or x, with probability p / 10, a random non-identity Pauli (X, Y or Z);
  * no readout error, no idle decoherence, no crosstalk.
This is a Monte-Carlo (Pauli-trajectory) simulation: each trial draws where errors strike,
evolves the exact state with those errors inserted, and the outcome distributions of all trials
are averaged. Gate matrices come from qiskit.quantum_info.Operator; no Qiskit Aer is used.

Each point reports the Monte-Carlo standard error of P(best) ("p_best_se"); at small gate errors
few trials contain any error, so the estimate is coarse there.

P(best) is the chance that one measurement returns the best 2-site network of the reduced
instance; "valid" is the chance that it returns exactly k sites at all (noise can break the
"exactly k" guarantee of the XY mixer).
"""
from __future__ import annotations

from itertools import combinations
from math import comb

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Operator

from .geometry import Instance, Scorer, load_instance
from .qaoa_solver import run_xy_qaoa, xy_qaoa_circuit
from .qubo import build_objective, energies, to_hamiltonian

LAM = 150.0                     # same risk weight as run_experiment.py
ONE_QUBIT_FACTOR = 0.1          # one-qubit gates get a tenth of the two-qubit error
BASIS = ["rz", "sx", "x", "cx"]
NOTE = ("Simulated depolarising noise (Monte-Carlo Pauli errors after each sx, x and cx gate; one-qubit "
        "error = gate_error / 10; no readout error). Not a hardware run.")

_ANGLES: dict[tuple, list] = {}        # tuned angles of the default (Ridgecrest) study, per process

_PAULI = {"I": np.eye(2), "X": np.array([[0, 1], [1, 0]], complex),
          "Y": np.array([[0, -1j], [1j, 0]]), "Z": np.diag([1.0 + 0j, -1.0])}


def transpiled_ops(qc: QuantumCircuit, seed: int = 0) -> tuple[list[tuple[np.ndarray, tuple[int, ...], str]], dict]:
    """Transpile to rz/sx/x/cx and return [(matrix, qubits, name)] plus gate counts."""
    t = transpile(qc, basis_gates=BASIS, optimization_level=1, seed_transpiler=seed)
    ops, counts = [], {"one_qubit": 0, "two_qubit": 0}
    for inst in t.data:
        name = inst.operation.name
        if name in ("barrier", "measure"):
            continue
        qubits = tuple(t.find_bit(q).index for q in inst.qubits)
        ops.append((Operator(inst.operation).data, qubits, name))
        if name == "cx":
            counts["two_qubit"] += 1
        elif name in ("sx", "x"):
            counts["one_qubit"] += 1
    return ops, counts


def _apply(state: np.ndarray, mat: np.ndarray, qubits: tuple[int, ...], n: int) -> np.ndarray:
    """Apply a k-qubit matrix (Qiskit little-endian on `qubits`) to an n-qubit state tensor."""
    k = len(qubits)
    m = mat.reshape([2] * (2 * k))                      # out_{k-1}..out_0, in_{k-1}..in_0
    axes = [n - 1 - q for q in reversed(qubits)]        # tensor axis of in_{k-1}..in_0
    out = np.tensordot(m, state, axes=(list(range(k, 2 * k)), axes))
    return np.moveaxis(out, list(range(k)), axes)


def _random_pauli(k: int, rng: np.random.Generator) -> np.ndarray:
    """A uniformly random non-identity Pauli on k qubits (little-endian matrix)."""
    labels = "IXYZ"
    while True:
        pick = rng.integers(0, 4, size=k)
        if pick.any():
            break
    mat = np.array([[1.0 + 0j]])
    for j in reversed(range(k)):                        # qubit k-1 is the most significant
        mat = np.kron(mat, _PAULI[labels[pick[j]]])
    return mat


def simulate(ops, n: int, rng: np.random.Generator, p2: float) -> np.ndarray:
    """One Pauli trajectory; returns the outcome probabilities (Qiskit index order)."""
    p1 = p2 * ONE_QUBIT_FACTOR
    state = np.zeros([2] * n, complex)
    state[(0,) * n] = 1.0
    for mat, qubits, name in ops:
        state = _apply(state, mat, qubits, n)
        p = p2 if name == "cx" else (p1 if name in ("sx", "x") else 0.0)
        if p and rng.random() < p:
            state = _apply(state, _random_pauli(len(qubits), rng), qubits, n)
    return np.abs(state.reshape(-1)) ** 2


def reduced_instance(inst: Instance, n: int, k: int, lam: float = LAM) -> tuple[Instance, list[int]]:
    """The n candidates with the largest single-site gain (D-score gain minus lam x risk)."""
    sc = Scorer(inst, inst.design)
    d0 = sc.d_score([])
    gain = np.array([sc.d_score([i]) - d0 - lam * float(inst.risk[i]) for i in range(inst.n)])
    sites = sorted(int(i) for i in np.argsort(-gain, kind="stable")[:n])
    sub = Instance(inst.design, inst.valid, inst.stations, inst.station_names, inst.candidates[sites],
                   inst.risk[sites], inst.mainshock, k=k, design_mag=inst.design_mag, valid_mag=inst.valid_mag)
    return sub, sites


def noise_study(inst: Instance | None = None, *, n: int = 6, k: int = 2, layers: int = 1,
                gate_errors=(0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2), trials: int = 200, seed: int = 0) -> dict:
    """P(best) and the valid fraction under simulated depolarising gate noise (shape of GET /noise)."""
    event_id = "ridgecrest2019" if inst is None else None
    inst = load_instance() if inst is None else inst
    sub, sites = reduced_instance(inst, n, k)
    obj = build_objective(sub, Scorer(sub, sub.design), LAM, order=k)    # exact for k sites
    h, _ = to_hamiltonian(obj)
    diag = energies(obj)
    weight = np.array([bin(i).count("1") for i in range(2**n)])
    feas = np.flatnonzero(weight == k)
    best = int(feas[np.argmin(diag[feas])])

    key = (n, k, layers, seed) if event_id else None
    theta = _ANGLES.get(key) if key else None
    if theta is None:                       # noise-free tuning; cached for the default instance
        theta = run_xy_qaoa(h, k, layers, seed=seed, restarts=4, shots=256, maxiter=200)["theta"]
        if key:
            _ANGLES[key] = theta
    qc = xy_qaoa_circuit(h, k, layers).assign_parameters(theta)
    ops, counts = transpiled_ops(qc, seed)
    clean = simulate(ops, n, np.random.default_rng(seed), 0.0)

    points = []
    for p in gate_errors:
        p = float(p)
        if p == 0.0:
            probs, se = clean, 0.0
        else:
            rng = np.random.default_rng([seed, int(round(p * 1e9))])
            runs = np.array([simulate(ops, n, rng, p) for _ in range(trials)])
            probs = runs.mean(axis=0)
            se = float(runs[:, best].std(ddof=1) / np.sqrt(trials)) if trials > 1 else None
        points.append(dict(gate_error=p, p_best=float(probs[best]), valid=float(probs[feas].sum()),
                           p_best_se=se))

    best_sites = [sites[i] for i in range(n) if best >> i & 1]
    return dict(instance=dict(n=n, k=k, layers=layers, event_id=event_id, sites=sites),
                points=points, uniform_p_best=1.0 / comb(n, k), note=NOTE,
                best_network=best_sites, trials=trials, gates=counts,
                angles=[float(a) for a in theta])
