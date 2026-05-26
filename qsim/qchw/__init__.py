"""qsim qchw plugin — quantum-computing hardware control & readout (domain #3, M4).

The final validation domain in the roadmap. M3 already ran a single spin-1/2 under Lindblad,
so M4 only earns its place by adding what M3 could not: genuinely MULTI-qubit Hilbert spaces
(tensor products), ENTANGLING gates, and the device-characterization metrics real QC-hardware
groups report. It hosts a noisy few-qubit processor on the unchanged kernel:

  * a multi-qubit density-matrix / Lindblad backend (qsim/qchw/backend.py) — a third
    QuantumStateBackend, with T1 amplitude damping + dephasing, a gate library incl. CNOT,
    and exact Pauli-transfer-matrix infidelities;
  * the QUANTUM_STATE signal carrying an n-qubit rho, plus CONTROL (gate/pulse schedule) and
    CLASSICAL (measurement outcomes) — exercising signal types QKD barely used;
  * the SAME MultiRateScheduler: slow qubit-parameter drift modulating fast shot batches.

Two-tier validation (mirrors M0/M1/M3):
  * Tier 1 (validation.validate_lindblad) — numeric Lindblad vs the closed-form T1 decay,
    T2 dephasing and undamped Rabi oscillation (backend-correctness gate);
  * Tier 2 (validation.validate_rb) — Randomized Benchmarking [Magesan et al., PRL 106,
    180504 (2011); PRA 85, 042311 (2012)], the industry-standard gate-fidelity protocol:
    the RB-fitted error-per-Clifford must match the INDEPENDENTLY-computed average gate
    infidelity of the injected T1/T2 noise channel (a non-circular check).

numpy-only: a dense rho is exact and transparent for the 1-2 qubit device-characterization
regime. The backend interface stays QuTiP-swappable for large-n scaling (sparse solvers).
"""
