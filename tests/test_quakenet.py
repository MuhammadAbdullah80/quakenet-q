"""Checks that the formulation and the quantum circuit do what the report claims."""
import warnings

import numpy as np
import pytest
from qiskit.quantum_info import Statevector

from src.baselines import (azimuthal_gap, backward_elimination, brute_force, expert_rule, greedy_forward,
                           simulated_annealing)
from src.location import dn_score, location_errors
from src.geometry import Scorer, load_instance
from src.qaoa_solver import cost_layer, dicke_probabilities, dicke_state, run_xy_qaoa, xy_qaoa_circuit
from src.qubo import build_objective, build_qubo, energies, to_hamiltonian

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


@pytest.fixture(scope="module")
def exact(inst, scorer):
    return build_objective(inst, scorer, LAM, order=4)


def test_order_4_objective_is_exact_for_every_4_site_network(inst, scorer, exact):
    base = scorer.d_score([])
    for s in inst.feasible_sets():
        truth = scorer.d_score(s) - LAM * inst.risk[list(s)].sum() - base
        assert exact.value(s) == pytest.approx(truth, abs=1e-6)


def test_exact_hamiltonian_matches_objective_on_every_basis_state(exact):
    h, const = to_hamiltonian(exact)
    assert {len(q) for _, q, _ in h.to_sparse_list()} == {1, 2, 3, 4}
    assert np.allclose(np.real(h.to_matrix(sparse=True).diagonal()) + const, energies(exact))


def test_cost_layer_applies_the_exact_phase_to_every_network(inst, exact):
    h, const = to_hamiltonian(exact)
    gamma = 0.37
    before = Statevector(dicke_state(inst.n, inst.k))
    qc = dicke_state(inst.n, inst.k)
    cost_layer(qc, h, gamma)
    expected = before.data * np.exp(-1j * gamma * (energies(exact) - const))
    assert np.allclose(Statevector(qc).data, expected)


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


def test_azimuthal_gap_of_four_compass_points_is_90_degrees():
    pts = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]])
    assert azimuthal_gap(pts, np.zeros(2)) == pytest.approx(90.0)


def test_expert_rule_fills_the_largest_gap_first():
    stations = np.array([[10.0, 0.0], [0.0, 10.0]])            # east and north only
    candidates = np.array([[9.0, 1.0], [-7.0, -7.0], [0.0, 9.0]])
    assert expert_rule(stations, candidates, np.zeros(2), k=1) == (1,)   # the south-west site


def test_location_error_shrinks_when_sensors_are_added(inst):
    events = inst.valid[:25]
    with_none = location_errors(inst, (), events, trials=1).mean()
    with_four = location_errors(inst, (0, 1, 4, 7), events, trials=1).mean()
    assert with_four < with_none


def test_dn_score_rewards_spread_over_duplication(inst):
    spread, bunched = (1, 4, 7, 8), (5, 6, 2, 3)
    assert np.isfinite(dn_score(inst, spread, inst.design))
    assert dn_score(inst, spread, inst.design) != dn_score(inst, bunched, inst.design)
