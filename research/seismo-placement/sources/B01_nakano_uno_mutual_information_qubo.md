# B01 - Quadratic Formulation of Mutual Information for Sensor Placement Optimization using Ising and Quantum Annealing Machines
- Authors: Yuta Nakano, Shigeyasu Uno (Ritsumeikan University)
- Year: 2024 (arXiv 2407.14747; submission date taken from search listing, not seen in PDF text)
- Venue: arXiv preprint (quant-ph); no peer-reviewed venue verified
- URL: https://arxiv.org/abs/2407.14747
- Type: preprint, method + toy demo
- Scores (1-5): credibility 2 (3-candidate demo only), recency 5, bias 3 (title claims quadratic; own discussion shows it is not beyond n=3)

## Verbatim quotes
1. "we defined mutual information (MI) between the data from selected sensor positions and the data from the others as an objective function, and formulated it in a Quadratic Unconstrainted Binary Optimization (QUBO) problem"
2. "the optimization often becomes Higher Order Binary Optimization (HOBO) involving functions with higher-order terms when the number of sensors is four or more."
3. "One approach to reduce such HOBO to QUBO is to determine the number of selected sensors in advance and add associated constraint terms to the objective function."

## How the objective is built (from PDF text; equations garbled by extraction, structure verified)
- Candidates ~ multivariate normal with covariance Sigma. Selected set S, complement Sbar. MI(S,Sbar) = 1/2 log( det Sigma_S * det Sigma_Sbar / det Sigma ). det Sigma is constant, so the objective is f = det(Sigma_S) * det(Sigma_Sbar).
- Trick: a masking matrix M (+1 / -1 / 0 according to whether i and j are both in S, both in Sbar, or split) is overlaid elementwise on Sigma; row/column swaps give a block-diagonal matrix, so det(Sigma o M) = det(Sigma_S) det(Sigma_Sbar). Expand with the Leibniz formula using Ising spins s_i (+1 in S, -1 in Sbar); each mask entry is a low-order polynomial in s_i, s_j.
- Result is a polynomial of high degree in the spins. Only for n=3 does it collapse to 2nd order (6th-order term is constant; 4th-order terms reduce because a spin repeats). For n=4: 8th, 6th and 4th order terms. General quadratisation is future work.
- Cardinality (choose k) not in the formulation; proposed as an added constraint term. Run on Fixstars Amplify AE and D-Wave, 3 candidates only; D-Wave returned some non-optimal states on toy B.

## Relevance
Only published quantum formulation of an information-theoretic (Gaussian MI) placement objective. NOT genuinely quadratic beyond n=3, so unusable at network scale as published. Concept only.
