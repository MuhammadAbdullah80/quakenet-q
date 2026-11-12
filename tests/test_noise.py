"""Simulated gate-noise study (a stand-in for a hardware run; no Aer)."""
import warnings

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from src.noise import NOTE, noise_study, simulate, transpiled_ops

warnings.filterwarnings("ignore")


@pytest.fixture(scope="module")
def study():
    return noise_study(trials=40, gate_errors=(0.0, 1e-3, 3e-2))


def test_shape_matches_the_api(study):
    assert study["instance"] == {"n": 6, "k": 2, "layers": 1, "event_id": "ridgecrest2019",
                                 "sites": study["instance"]["sites"]}
    assert len(study["instance"]["sites"]) == 6
    assert [p["gate_error"] for p in study["points"]] == [0.0, 1e-3, 3e-2]
    assert study["uniform_p_best"] == pytest.approx(1 / 15)
    assert study["note"] == NOTE and "Not a hardware run" in NOTE and "simulated" in NOTE.lower()


def test_noise_free_point_is_exact_and_valid(study):
    p0 = study["points"][0]
    assert p0["valid"] == pytest.approx(1.0)
    assert p0["p_best"] > study["uniform_p_best"]


def test_noise_lowers_validity_and_success(study):
    p0, p_hi = study["points"][0], study["points"][-1]
    assert p_hi["valid"] < p0["valid"] - 0.05
    assert p_hi["p_best"] < p0["p_best"]


def test_study_is_deterministic():
    a = noise_study(trials=10, gate_errors=(0.0, 1e-2))
    b = noise_study(trials=10, gate_errors=(0.0, 1e-2))
    assert a["points"] == b["points"]


def test_simulator_matches_statevector_without_noise():
    qc = QuantumCircuit(3)
    qc.h(0)
    qc.cx(0, 2)
    qc.ry(0.3, 1)
    qc.cx(1, 0)
    qc.sx(2)
    ops, _ = transpiled_ops(qc)
    probs = simulate(ops, 3, np.random.default_rng(0), p2=0.0)
    assert np.allclose(probs, Statevector(qc).probabilities(), atol=1e-10)
