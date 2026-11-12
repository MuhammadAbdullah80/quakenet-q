# C05 Qiskit 2.6.2 local API checks
- Type: local run | Scores: reliability 5, relevance 5
- Signature: QAOAAnsatz.__init__(self, cost_operator=None, reps=1, initial_state: QuantumCircuit|None=None, mixer_operator=None, name='QAOA', flatten=None)
- Test: 4 qubits, cost = SparsePauliOp ZZ/Z terms, initial_state = X on qubits 0,1 (Hamming weight 2), mixer_operator = SparsePauliOp sum 0.5*(XX+YY) over ring pairs (i,i+1 mod 4), reps=2.
  Result: params=4 (2 gamma+2 beta); StatevectorEstimator().run([(ansatz,cost,params)]) worked (<H>=0.6637); StatevectorSampler on measure_all copy worked; output bitstrings only {0011,0101,0110,1001,1010,1100} = weight 2 -> XY ring mixer conserves cardinality k. Note: ring XX and YY terms commute pairwise only partly but evolution via PauliEvolutionGate (Trotter default) still preserved weight here. Decompose(reps=3) -> cx 40, h 32, rz 20 etc.
- Gotchas: scipy SparseEfficiencyWarning noise from expm (harmless). Use initial_state circuit for Dicke state (prepare via X on first k qubits for simple version). Parameter order in ansatz.parameters: betas then gammas (check ansatz.parameters).
