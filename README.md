# qsim — open-source quantum-device simulation platform

A device-level, physically-realistic, **multi-rate** simulation platform — a *virtual
quantum bench* — for quantum-technology R&D. Mission: let low-budget researchers and
students (especially in developing countries) do the hard "tuning" work (custom boards,
control loops, calibration, stability, side-channels) **virtually**, where commercial
photonic-EDA tools are expensive and closed.

Architecture: a **domain-agnostic kernel** (`qsim.core`) + **per-domain plugins**.
Validation domains, in order: **(1) QKD → (2) quantum sensing → (3) quantum-computing
hardware**. The kernel never imports a plugin.

- Architecture & first reference design: [`docs/01_architecture_and_bom.md`](docs/01_architecture_and_bom.md)
- Kernel specification: [`docs/02_simulator_kernel_spec.md`](docs/02_simulator_kernel_spec.md)

## Status — M0 (multi-rate engine, validated)

M0 attacks the #1 technical risk: does the **multi-rate engine** (slow drift/control ×
fast batched pulse physics) work, stay fast on a laptop, and — crucially — produce the
*right answer*? It runs one QKD vertical slice:

```
FaintPulseSource → FiberChannel → BobAMZI(+phase drift) → GatedInGaAsDetector
```

with realistic, **provenance-tagged** impairments (efficiency, dark counts, history-
dependent afterpulsing, dead time, slow OU phase drift) and accumulates QBER by batches.

### Make-or-break: validated against a brute-force reference

The engine's whole premise is three approximations — (1) freezing the slow state per
batch, (2) mean-field impairments, (3) statistical batch aggregation. We don't assert they
are accurate; we **prove it** against a sequential per-gate ground truth
(`qsim/qkd/bruteforce.py`), matched by *physical duration* (see `demos/m0_validation.py`):

- **Correctness.** Batched vs brute-force agree on QBER to **<0.25% absolute** and on gain
  to a few %, across 10–100 km. The freeze-slow-state approximation, isolated with a
  *shared* drift trajectory, is essentially exact (≈0σ): the phase moves ~0.01 rad within a
  batch, far too little to matter.
- **One identified systematic (~0.1% QBER).** The mean-field afterpulse runs slightly high
  because it smears afterpulse probability over all gates, while real afterpulses cluster in
  the post-click **dead time** and are partly vetoed. It is bounded, click-rate-dependent,
  and far below input-parameter calibration uncertainty — a fidelity knob, not a blocker.
- **Speed / scaling.** The batched cost is **decoupled from the pulse rate** (∝ run time ÷
  slow-clock step), while brute-force must touch every gate. Simulating one hour at 100 MHz:
  brute-force ≈ 3.6×10¹¹ sequential gates (~30 h here), batched ≈ minutes.

`pytest tests/test_validation.py` enforces this agreement on every run.

## Install & run

```bash
pip install -e .            # or: pip install numpy scipy matplotlib pyyaml
python -m demos.m0_qber_demo      # QKD physics: QBER/SKR vs distance, phase-lock OFF vs ON
python -m demos.m0_validation     # the make-or-break: batched engine vs brute-force ground truth
pytest -q
```

Outputs (`demos/figures/`):
- `qber_skr_vs_distance.png` — classic QBER & secret-key-rate vs fiber length.
- `qber_timeseries.png` — QBER over time, phase-lock OFF vs ON (the multi-rate demo).
- `m0_validation.png` — correctness (batched vs ground truth) + scaling (cost vs pulse rate).

## Honesty notes

- The M0 secret-key rate uses a **simplified asymptotic** BB84 bound, not the full
  decoy-state finite-key bound — that (and validation against a published experiment) is
  the **M1** milestone. Do not quote M0 SKR as production figures.
- Impairment values are datasheet/paper-class defaults; tighten against real measurements
  before any quantitative claim (see `qsim/profiles/ingaas_spad.yaml` for provenance).
- The brute-force validation checks the **aggregation approximation** against a per-event
  simulation of the *same behavioral physics* — it does **not** validate that physics
  against reality. That requires matching a published experiment (the **M1** milestone).
- The mean-field afterpulse carries a known **~0.1% QBER** systematic vs the per-event model
  (dead-time vetoing, see above). Acceptable for M0; revisit if a use case needs that floor.

## Layout

```
qsim/core/      kernel: signals, block, graph, scheduler, backends, impairments, calibration, probes
qsim/qkd/       QKD plugin: blocks, metrics, reference slice builder,
                bruteforce (per-pulse ground truth), validation (engine-vs-truth harness)
qsim/profiles/  calibration profiles (YAML, with provenance)
demos/          m0_qber_demo (physics) + m0_validation (make-or-break: correctness & scaling)
tests/          sanity tests (test_m0) + engine validation (test_validation)
docs/           architecture (01) + kernel spec (02)
```

## Roadmap

M0 kernel+QKD slice (this) → M1 full decoy-BB84 + experiment validation → M2 calibration
framework + QRNG plugin + tuning UX → M3 sensing plugin (Bloch/QuTiP) → M4 QC-hardware
plugin (Lindblad/QuTiP).
