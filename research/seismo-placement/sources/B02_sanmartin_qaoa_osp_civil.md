# B02 - Quantum-Based Combinatorial Optimization for Optimal Sensor Placement in Civil Structures
- Authors: Gabriel San Martin, Enrique Lopez Droguett (UCLA)
- Year: arXiv May 2023 (2305.08738, first posted 2023-05-03). Journal version 2024 (Structural Control and Health Monitoring) is from the task brief: UNVERIFIED by me; the PDF I read has no venue line.
- URL: https://arxiv.org/abs/2305.08738
- Type: preprint (journal version unverified); method + PennyLane simulation
- Scores: credibility 3, recency 4, bias 2 (candid limitations section)

## Verbatim quotes
1. "a Quadratic Unconstrained Binary Optimization (QUBO) model formulation is developed, taking as a starting point the modal strain energy (MSE) of the structure."
2. "This initial state assigns equal probabilities to all those states that contain exactly"  (continues: "k entries equal to one.")
3. "the XY mixer consistently outperforms the Traditional Hamiltonian across all cases."

## Formulation (verified)
- MSE criterion is a double sum over DOFs of (modal-shape x stiffness) coefficients. Introducing binary x_m (DOF m selected) gives their Eq. 53: sum_m sum_n c_mn x_m x_n, quadratic because the criterion is already bilinear in the selection indicators. Maximise s.t. sum x = k (Eq. 55).
- Constraint two ways: (a) penalty lambda (sum x - k)^2 with standard transverse-field mixer; (b) XY mixer with Dicke initial state |D_k^n>, which keeps Hamming weight k and removes lambda, at cost of more gates and only for equality constraints of that form.
- Warren truss WT5 and WT11; PennyLane 0.33.1 simulator only, no hardware. XY+Dicke beat penalty; probability of sampling the optimum is low and shrinks with size; ADAM optimiser.

## Relevance
Best template for QAOA with exact-k cardinality. The pattern to copy: use a criterion that is bilinear in selection indicators (x^T A x) so QUBO is exact, not approximate.
