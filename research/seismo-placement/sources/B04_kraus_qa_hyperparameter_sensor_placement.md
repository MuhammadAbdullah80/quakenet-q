# B04 - Quantum Annealing Hyperparameter Analysis for Optimal Sensor Placement in Production Environments
- Authors: Nico Kraus, Marvin Erdmann, Alexander Kuzmany, Daniel Porawski, Jonas Stein (Aqarios, BMW Group, LMU Munich)
- Year: 2025 (arXiv 2507.16584v1, 22 Jul 2025)
- URL: https://arxiv.org/abs/2507.16584
- Type: preprint; empirical D-Wave Advantage 4.1 study
- Scores: credibility 3, recency 5, bias 2 (candid that classical wins)

## Verbatim quotes
1. "Despite these findings, classical algorithms continue to significantly outperform quantum annealing."
2. "A major challenge remains the substantial number of slack variables required to encode the derived QUBO problem"
3. "To mitigate the issue of excessive slack variables, constrained mixer Hamiltonians can be employed in the quantum approximate optimization algorithm (QAOA)"

## Formulation (verified)
- Set cover on a bipartite graph (LiDAR positions x_l, street points s). Minimise sum x_l s.t. sum_{l in N_s} x_l >= 1. The inequality becomes an equality with slack y_s >= 0; penalty lambda (sum_{N_s} x_l - y_s - 1)^2; y_s encoded one-hot or binary (log2|N_s| bits). Binary encoding was better.
- Best settings: lambda 0.1-0.2 (below 1), chain-strength factor 0.5, anneal time 500 us. Up to 4109 qubits only with decomposition; direct embedding to 879 qubits (Real 6).

## Relevance
Template for a "each cell/fault segment seen by >= 1 (or m) stations" coverage objective. Warns that slack qubits dominate size and classical solvers still win: a sober baseline for any quantum-advantage claim.
