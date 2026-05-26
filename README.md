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

## Status — M1 (decoy-BB84 reference design + finite-key, validated)

M1 turns the engine into the real device from [`docs/01`](docs/01_architecture_and_bom.md):
**1-decoy-state BB84** (Rusca et al. 2018, the protocol named in §0), with the proper
composably-secure **finite-key** bound replacing M0's placeholder asymptotic fraction.

- **Finite-key core** (`qsim/qkd/finite_key.py`): a pure, independent implementation of
  Rusca 2018 (arXiv:1801.03443) — vacuum/single-photon bounds, X-basis phase-error, and the
  secret-key length, with Hoeffding finite-statistics.
- **Validated vs the published figure** (`demos/m1_rusca_validation.py`): our implementation
  reproduces Rusca's SKR-vs-attenuation figure — **n_Z=10⁷ → ~180 kHz at 26 dB (paper
  ~200 kHz) and ~62 dB reach (paper ~60–64 dB)**, with the correct plateau, slope, and
  block-size ordering. This is the credibility step (matching a published result).
- **End-to-end through the engine** (`demos/m1_engine_skr.py`): the decoy source + sifting
  detector accumulate per-(basis, intensity) counts under the *full M0 impairments*
  (afterpulse, phase drift, dead time); the finite-key bound turns them into a proven SKR.
  A control-loop choice (AMZI phase-lock ON/OFF) flows all the way to the key: lock off →
  X-basis error inflates → phase-error bound rises → the proven key collapses at distance.

`pytest tests/test_finite_key.py tests/test_decoy_engine.py` covers both.

## Status — M2 (productizing the tuning loop + proving modularity)

M2 turns the device model into a usable **virtual bench** and shows the kernel is not
QKD-shaped:

- **Sweep / optimize harness** (`qsim/core/sweep.py`) — domain-agnostic `sweep(run_fn, grid)`
  (with 2-D surfaces) and `optimize(run_fn, bounds, metric)`. The "vary a knob, watch the
  metric" UX. Demo `m2_tuning_loop.py` finds the SKR-optimal intensity (μ₁≈0.62) and maps
  the (μ₁, p_Z) sensitivity surface.
- **QRNG plugin** (`qsim/qrng/`) — a beam-splitter QRNG built from the **same kernel
  primitives, zero new kernel code** (spec §10). Min-entropy metric: balanced detectors →
  0.9995 bits/bit; efficiency mismatch → less extractable randomness. Proof of modularity.
- **Declarative scenarios** (`qsim/core/scenario.py` + `scenarios/*.yaml`) — an experiment is
  one shareable file naming a registered runner + params; plugins register runners on import
  (the kernel never imports a plugin).
- **Interactive notebook** (`notebooks/M2_tuning_loop.ipynb`) — build → run → sweep/optimize →
  read a validated metric, across both domains.

Still open in M2: a richer calibration/uncertainty-propagation framework and a web GUI.

## Install & run

```bash
pip install -e .            # or: pip install numpy scipy matplotlib pyyaml
python -m demos.m0_qber_demo        # M0 physics: QBER/SKR vs distance, phase-lock OFF vs ON
python -m demos.m0_validation       # M0 make-or-break: batched engine vs brute-force ground truth
python -m demos.m1_rusca_validation # M1 credibility: reproduce Rusca 2018 finite-key SKR figure
python -m demos.m1_engine_skr       # M1 capstone: engine-driven proven SKR, phase-lock ON vs OFF
python -m demos.m2_tuning_loop      # M2 tuning loop: sweep/optimize the SKR over mu1, p_Z
jupyter notebook notebooks/M2_tuning_loop.ipynb   # M2 interactive virtual bench
pytest -q
```

Outputs (`demos/figures/`):
- `qber_skr_vs_distance.png` — classic QBER & secret-key-rate vs fiber length.
- `qber_timeseries.png` — QBER over time, phase-lock OFF vs ON (the multi-rate demo).
- `m0_validation.png` — correctness (batched vs ground truth) + scaling (cost vs pulse rate).
- `m1_rusca_validation.png` — finite-key SKR vs attenuation (cf. Rusca 2018, 4 block sizes).
- `m1_engine_skr.png` — engine-driven proven SKR vs distance, phase-lock ON vs OFF.

## Honesty notes

- M0's `metrics.secret_fraction` is a **simplified asymptotic** placeholder; M1's
  `finite_key.secret_key_length` (Rusca 2018) is the real composably-secure bound — use the
  latter for any SKR claim.
- The M1 finite-key validation reproduces Rusca's **simulated** figure (a channel model +
  the bound), confirming our bound implementation. It is **not yet** a match to a hardware
  experiment with measured detector data — that is the higher bar for a production claim.
- Two documented finite-key implementation choices (the `s_{Z,0}^u` intensity pick → tighter
  min; natural-log Hoeffding term) are resolved by that figure match to within ~2 dB reach;
  the residual is the dark-count/dead-time convention.
- Impairment values are datasheet/paper-class defaults; tighten against real measurements
  before any quantitative claim (see `qsim/profiles/ingaas_spad.yaml` for provenance).
- The brute-force validation checks the engine's **aggregation approximation** against a
  per-event simulation of the *same behavioral physics* — not that physics against reality.
- The mean-field afterpulse carries a known **~0.1% QBER** systematic vs the per-event model
  (dead-time vetoing). Acceptable here; revisit if a use case needs that floor.

## Layout

```
qsim/core/      kernel: signals, block, graph, scheduler, backends, impairments, calibration,
                probes, sweep (tuning loop), scenario (declarative experiments)
qsim/qkd/       QKD plugin: blocks (M0 + decoy-BB84), reference builders, metrics,
                bruteforce (M0 ground truth), validation, finite_key (Rusca 2018),
                channel (decoy model), keyrate (SKR optimise/scale), scenarios
qsim/qrng/      QRNG plugin: beam-splitter QRNG built from kernel primitives (modularity)
qsim/profiles/  calibration profiles (YAML, with provenance)
scenarios/      declarative experiment files (decoy_bb84_25km.yaml, qrng_balanced.yaml)
demos/          m0_qber_demo, m0_validation, m1_rusca_validation, m1_engine_skr, m2_tuning_loop
notebooks/      M0_qber_demo, M2_tuning_loop (interactive virtual bench)
tests/          test_m0, test_validation, test_finite_key, test_decoy_engine, test_sweep,
                test_qrng, test_scenario
docs/           architecture (01) + kernel spec (02)
```

## Roadmap

M0 kernel+QKD slice ✓ → M1 decoy-BB84 + finite-key (Rusca 2018), validated vs published
figure ✓ → M2 sweep/optimize + scenario files + QRNG plugin + Jupyter UX ✓ (calibration-
uncertainty framework + web GUI still open) → M3 sensing plugin (Bloch/QuTiP) → M4
QC-hardware plugin (Lindblad/QuTiP).

Next for M1 to reach a *production*-grade claim: match a hardware experiment with measured
detector data (vs the current published-simulation match), and fold dead-time into the
finite-key rate rather than as a post-hoc cap.
