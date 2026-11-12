"""CVaR objective and warm start of the XY-mixer QAOA (small 5-qubit fixtures)."""
import warnings

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from src.qaoa_solver import cvar_value, diagonal, run_xy_qaoa

warnings.filterwarnings("ignore")


def toy_h():
    # 5 sites, choose 2: a diagonal Hamiltonian with a clear best pair.
    rng = np.random.default_rng(3)
    ops = [("Z", [i], float(rng.normal())) for i in range(5)]
    ops += [("ZZ", [i, j], float(rng.normal()) * 0.5) for i in range(5) for j in range(i + 1, 5)]
    return SparsePauliOp.from_sparse_list(ops, num_qubits=5)


def test_cvar_value_of_a_known_distribution():
    diag = np.array([3.0, 1.0, 2.0, 0.0])
    probs = np.array([0.1, 0.2, 0.3, 0.4])
    assert cvar_value(probs, diag, 1.0) == pytest.approx(probs @ diag)       # alpha = 1 is the mean
    assert cvar_value(probs, diag, 0.4) == pytest.approx(0.0)                # only the best state
    assert cvar_value(probs, diag, 0.5) == pytest.approx((0.4 * 0 + 0.1 * 1) / 0.5)


def test_diagonal_matches_the_pauli_operator():
    h = toy_h()
    assert np.allclose(diagonal(h), np.real(np.diag(h.to_matrix())))


def test_default_run_is_unchanged_and_says_mean():
    h = toy_h()
    a = run_xy_qaoa(h, 2, 1, seed=1, restarts=1, shots=256, maxiter=40)
    b = run_xy_qaoa(h, 2, 1, seed=1, restarts=1, shots=256, maxiter=40, cvar_alpha=None)
    assert a["objective"] == "mean" and a["theta"] == b["theta"] and a["energy"] == b["energy"]


def test_cvar_run_reaches_alpha_on_the_best_state():
    h = toy_h()
    diag = diagonal(h)
    ones = np.array([bin(i).count("1") for i in range(32)])
    feas = np.where(ones == 2)[0]
    best = feas[np.argmin(diag[feas])]
    mean = run_xy_qaoa(h, 2, 2, seed=0, restarts=2, shots=256, maxiter=80)
    cvar = run_xy_qaoa(h, 2, 2, seed=0, restarts=2, shots=256, maxiter=80, cvar_alpha=0.1, diag=diag)
    assert cvar["objective"] == "cvar"
    # CVaR at alpha only rewards the best alpha of the probability mass: once P(best) >= alpha the
    # objective is flat, so the guarantee is P(best) >= alpha and a CVaR no worse than the mean run's.
    assert cvar["probs"][best] >= 0.1 - 1e-3
    assert cvar["cvar"] <= cvar_value(mean["probs"], diag, 0.1) + 1e-6
    assert cvar["probs"][feas].sum() == pytest.approx(1.0)          # XY mixer keeps every sample valid
    assert np.isfinite(cvar["energy"])


def test_warm_start_only_uses_the_given_angles_with_no_restarts():
    h = toy_h()
    cold = run_xy_qaoa(h, 2, 1, seed=0, restarts=2, shots=128, maxiter=60, cvar_alpha=0.2)
    warm = run_xy_qaoa(h, 2, 1, seed=5, restarts=0, shots=128, maxiter=60, cvar_alpha=0.2,
                       init=cold["theta"])
    assert warm["cvar"] <= cold["cvar"] + 1e-6


def test_bad_alpha_is_refused():
    with pytest.raises(ValueError):
        run_xy_qaoa(toy_h(), 2, 1, cvar_alpha=0.0)


def test_fast_simulator_matches_the_circuit():
    from qiskit.quantum_info import Statevector
    from src.qaoa_solver import XYQaoaSimulator, xy_qaoa_circuit
    h = toy_h()
    theta = [0.3, -0.7, 0.45, 1.1]                      # beta0, beta1, gamma0, gamma1
    sim = XYQaoaSimulator(h, 2, 2)
    exact = Statevector(xy_qaoa_circuit(h, 2, 2).assign_parameters(theta)).probabilities()
    assert np.allclose(sim.probabilities(theta), exact, atol=1e-10)
