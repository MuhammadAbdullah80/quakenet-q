"""Checks that the formulation and the quantum circuit do what the report claims."""
import warnings

import numpy as np
import pytest
from qiskit.quantum_info import Statevector

from src.baselines import backward_elimination, brute_force, greedy_forward, simulated_annealing
from src.geometry import Scorer, load_instance
from src.qaoa_solver import dicke_probabilities, dicke_state, run_xy_qaoa, xy_qaoa_circuit
from src.qubo import build_qubo, energies, to_hamiltonian

warnings.filterwarnings("ignore")
LAM = 150.0


@pytest.fixture(scope="module")
def inst():
    return load_instance()


@pytest.fixture(scope="module")
def scorer(inst):
    return Scorer(inst, inst.design)


@pytest.fixture(scope="module")
def qubo(inst, scorer):
    return build_qubo(inst, scorer, LAM)


def test_instance_uses_real_data_split_by_time(inst):
    assert inst.n == 10 and inst.k == 4
    assert len(inst.stations) == 14
    assert len(inst.design) > 100 and len(inst.valid) > 100
    assert len(inst.feasible_sets()) == 210


def test_adding_a_station_never_reduces_information(inst, scorer):
    base = scorer.d_score([])
    for i in range(inst.n):
        assert scorer.d_score([i]) > base
    assert scorer.d_score([0, 1]) > scorer.d_score([0])


def test_more_stations_means_less_blur(scorer):
    assert scorer.blur_km([0, 1, 4, 7]) < scorer.blur_km([0, 1]) < scorer.blur_km([])


def test_qubo_is_exact_for_one_and_two_sites(inst, scorer):
    q = build_qubo(inst, scorer, lam=0.0)
    d0 = scorer.d_score([])
    assert q.value([3]) == pytest.approx(scorer.d_score([3]) - d0)
    assert q.value([2, 7]) == pytest.approx(scorer.d_score([2, 7]) - d0)


def test_hamiltonian_matches_qubo_on_every_allowed_network(inst, qubo):
    h, const = to_hamiltonian(qubo)
    diag = np.real(h.to_matrix(sparse=True).diagonal()) + const
    e = energies(qubo)
    assert np.allclose(diag, e)
    for s in inst.feasible_sets():
        assert e[sum(1 << i for i in s)] == pytest.approx(-qubo.value(s) / qubo.scale)


def test_penalty_hamiltonian_adds_constraint_violation(qubo):
    h, const = to_hamiltonian(qubo, penalty=2.0, k=4)
    diag = np.real(h.to_matrix(sparse=True).diagonal()) + const
    assert np.allclose(diag, energies(qubo, penalty=2.0, k=4))


@pytest.mark.parametrize("n,k", [(4, 2), (5, 1), (6, 3), (10, 4)])
def test_dicke_circuit_is_uniform_over_allowed_networks(n, k):
    probs = Statevector(dicke_state(n, k)).probabilities()
    assert np.allclose(probs, dicke_probabilities(n, k))


def test_xy_mixer_never_leaves_the_allowed_networks(inst, qubo):
    h, _ = to_hamiltonian(qubo)
    qc = xy_qaoa_circuit(h, inst.k, reps=2)
    theta = np.random.default_rng(1).uniform(-2, 2, qc.num_parameters)
    probs = Statevector(qc.assign_parameters(theta)).probabilities()
    allowed = dicke_probabilities(inst.n, inst.k) > 0
    assert probs[allowed].sum() == pytest.approx(1.0)


def test_qaoa_beats_uniform_sampling_of_allowed_networks(inst, qubo):
    h, _ = to_hamiltonian(qubo)
    res = run_xy_qaoa(h, inst.k, reps=1, seed=0, restarts=1, shots=256)
    e = energies(qubo)
    best = min(inst.feasible_sets(), key=lambda s: e[sum(1 << i for i in s)])
    p_opt = res["probs"][sum(1 << i for i in best)]
    assert p_opt > 2 / 210                       # uniform would give 1/210
    assert all(len(s) == inst.k for s in res["counts"])


def test_brute_force_is_never_beaten(inst, qubo):
    best = qubo.value(brute_force(inst.n, inst.k, qubo.value))
    for method in (greedy_forward, backward_elimination, simulated_annealing):
        picked = method(inst.n, inst.k, qubo.value)
        assert len(set(picked)) == inst.k
        assert qubo.value(picked) <= best + 1e-9
