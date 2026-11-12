# C06 qiskit-optimization compatibility
- Local: `import qiskit_optimization` -> ModuleNotFoundError (not installed; nothing installed by me).
- `pip index versions qiskit-optimization`: latest 0.7.0 (also 0.6.1 ...).
- Downloaded wheel metadata only (to temp dir, not installed): "Version: 0.7.0", "Requires-Dist: qiskit<3,>=1.1" -> declared compatible with Qiskit 2.6.2. Not tested at runtime. Not needed: SparsePauliOp + QAOAAnsatz suffice. Scores: reliability 4, relevance 3.
