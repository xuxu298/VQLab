"""qsim sensing plugin — an optically-pumped atomic magnetometer.

M3 milestone: the *generality* test. QKD and QRNG both live in the photon/Fock world; an
atomic magnetometer is physically unlike them, so it stresses the parts of the kernel that
M0-M2 never touched:

  * a brand-new quantum-state backend — a spin density-matrix / Bloch-Lindblad evolver, not
    photon-number statistics (proves the QuantumStateBackend interface isn't secretly
    photon-shaped — see qsim/sensing/backend.py);
  * the ENVIRONMENTAL signal type, which QKD *defined but never used* — the B-field being
    sensed finally flows on it (proves it wasn't dead weight);
  * the SAME MultiRateScheduler, unchanged: a slowly-drifting field modulating fast batches
    of measurement cycles — structurally identical to QKD's "slow phase drift modulates fast
    pulse batches -> QBER", here "slow field drift -> field estimate + sensitivity";
  * the SAME sweep/scenario harness, with zero kernel edits.

Validation is two-tier, mirroring M0/M1:
  * Tier 1 (validation.py:validate_bloch) — the numeric integrator vs the closed-form
    Larmor precession + T2 decay and T1 recovery (the backend-correctness gate, M0 analog);
  * Tier 2 (validation.py:validate_sensitivity) — Monte-Carlo device sensitivity vs the
    published spin-projection-noise limit dB = 1/(gamma*sqrt(N*T2*t)) (Budker & Romalis,
    "Optical magnetometry", Nature Physics 3, 227 (2007)) — the credibility milestone (M1
    analog).
"""
