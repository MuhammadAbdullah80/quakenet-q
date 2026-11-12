# B03 - Solving Sensor Placement Problems In Real Water Distribution Networks Using Adiabatic Quantum Computation
- Authors: Stefano Speziali, Federico Bianchi, Andrea Marini, Lorenzo Menculini, Massimiliano Proietti, Loris F. Termite, Alberto Garinei, Marcello Marconi, Andrea Delogu
- Year: 2021 (arXiv 2108.04075v2, 20 Aug 2021); conference venue not verified
- URL: https://arxiv.org/abs/2108.04075
- Type: preprint/conference; applied QUBO + D-Wave hybrid
- Scores: credibility 3, recency 3, bias 2

## Verbatim quotes
1. "we formulate the problem of correctly placing pressure sensors on a Water Distribution Network as a combinatorial optimization problem in the form of a Quadratic Unconstrained Binary Optimization (QUBO) or Ising model."
2. "The problem of covering our WDN with pressure sensors can be formulated as the minimum vertex cover problem"

## Formulation (verified)
- x_i = 1 if node i hosts a sensor. H0 = A * sum_(ij in E) w_ij (1-x_i)(1-x_j): penalises uncovered edges (vertex cover; natively quadratic). H1 = sum_i c_i x_i with c_i = C f_i + D g_i (accessibility, water demand). H2 = B (sum_i x_i - s)^2 for exactly s sensors. For "at most s": one-hot slack y_l with H2~ = B(1 - sum_l y_l)^2 + B(sum_l l*y_l - sum_i x_i)^2. H = H0+H1+H2, four hyperparameters A,B,C,D.
- Neither Chimera nor Pegasus embedding was big enough for the real network, so the hybrid Leap solver was used.

## Relevance
Cleanest graph-coverage template: stations = vertices, edges = coverage relations weighted by importance. Natively quadratic; cardinality by squared penalty.
