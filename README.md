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

## Status — M0 (proof of concept)

M0 attacks the #1 technical risk: does the **multi-rate engine** (slow drift/control ×
fast batched pulse physics) work and stay fast on a laptop? It runs one QKD vertical slice:

```
FaintPulseSource → FiberChannel → BobAMZI(+phase drift) → GatedInGaAsDetector
```

with realistic, **provenance-tagged** impairments (efficiency, dark counts, history-
dependent afterpulsing, dead time, slow OU phase drift) and accumulates QBER by batches.

## Install & run

```bash
pip install -e .            # or: pip install numpy scipy matplotlib pyyaml
python -m demos.m0_qber_demo
pytest -q
```

Outputs (`demos/figures/`):
- `qber_skr_vs_distance.png` — classic QBER & secret-key-rate vs fiber length.
- `qber_timeseries.png` — QBER over time, phase-lock OFF vs ON (the multi-rate demo).

## Honesty notes

- The M0 secret-key rate uses a **simplified asymptotic** BB84 bound, not the full
  decoy-state finite-key bound — that (and validation against a published experiment) is
  the **M1** milestone. Do not quote M0 SKR as production figures.
- Impairment values are datasheet/paper-class defaults; tighten against real measurements
  before any quantitative claim (see `qsim/profiles/ingaas_spad.yaml` for provenance).

## Layout

```
qsim/core/      kernel: signals, block, graph, scheduler, backends, impairments, calibration, probes
qsim/qkd/       QKD plugin: blocks, metrics, reference slice builder
qsim/profiles/  calibration profiles (YAML, with provenance)
demos/          runnable demos
tests/          sanity tests
docs/           architecture (01) + kernel spec (02)
```

## Roadmap

M0 kernel+QKD slice (this) → M1 full decoy-BB84 + experiment validation → M2 calibration
framework + QRNG plugin + tuning UX → M3 sensing plugin (Bloch/QuTiP) → M4 QC-hardware
plugin (Lindblad/QuTiP).
