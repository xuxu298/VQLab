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

## Status — M3 (the kernel-generality proof: a sensing device)

M3 answers the question that matters most for a *platform*: is the kernel actually
domain-general, or secretly QKD-shaped? It hosts a physically unrelated device — an
optically-pumped **atomic magnetometer** — and the kernel takes **zero edits**:

- **New quantum-state backend** (`qsim/sensing/backend.py`) — a spin Bloch/Lindblad evolver,
  not photon-number statistics. The kernel never calls a backend directly (only domain blocks
  do), so a new physics domain = new backend class + new blocks, no kernel change. numpy-only;
  QuTiP is deferred to M4 (multi-qubit) where it earns its weight.
- **The ENVIRONMENTAL signal type** — defined in M0 but *never used by QKD* — finally flows:
  the B-field under test is emitted by `AmbientField`. Plus a new plugin-local `SpinBatch`
  payload runs through the **unchanged** `MultiRateScheduler` (it passes the batch opaquely),
  proving the scheduler is payload-agnostic.
- **Same multi-rate structure as QKD**: slow ambient-field drift (reusing `PhaseDriftOU`)
  modulating fast batches of measurement cycles — structurally identical to "slow phase drift
  → QBER", here "slow field drift → field estimate + sensitivity".
- **Two-tier validation** (`qsim/sensing/validation.py`), mirroring M0/M1:
  - *backend correctness* — the RK4 Bloch integrator matches the closed-form Larmor
    precession + T₂/T₁ relaxation to **~7×10⁻¹⁰** (analog of M0's brute-force check);
  - *physics/metric* — Monte-Carlo device sensitivity reproduces the published
    spin-projection-noise limit δB = 1/(γ√(N·T₂·t)) [Budker & Romalis, *Nature Physics* 3,
    227 (2007)]: correct 1/√N and 1/√t scaling, with an honestly-reported O(1) readout
    prefactor (= e at τ=T₂, exactly as derived). The analog of M1's Rusca-figure match.
- **Harness reuse**: the same `sweep()` maps sensitivity vs atom number (slope −1/2); the
  device runs as a one-line scenario (`scenarios/magnetometer_rb.yaml`, `kind: magnetometer`).

## Status — M4 (the third domain: multi-qubit QC hardware)

M4 closes the roadmap's domain list by hosting the most demanding domain — a noisy few-qubit
processor — on the unchanged kernel. M3 already ran a single spin-½, so M4 earns its place
only with capability M3 *could not* show: **multi-qubit Hilbert spaces and entanglement**.

- **Third quantum-state backend** (`qsim/qchw/backend.py`) — a multi-qubit density-matrix /
  Lindblad evolver (T1 amplitude damping + dephasing), a gate library incl. the entangling
  **CNOT**, and exact average-gate-infidelity via the Pauli transfer matrix. numpy-only and
  transparent for 1–2 qubits; the interface stays QuTiP-swappable for large-n scaling.
- **Multi-qubit + entanglement**: a Bell pair (H, CNOT) reaches **unit fidelity** ideally and
  degrades realistically under T1/T2 (≈99.87 % over 40 ns gates) and miscalibration — the
  tensor-product/entangling physics that distinguishes M4 from M3's single qubit.
- **Two-tier validation** (`qsim/qchw/validation.py`):
  - *backend correctness* — the Lindblad propagator matches the closed-form T1 decay, T2
    dephasing and undamped Rabi to **machine precision** (expm is exact);
  - *physics/metric* — **Randomized Benchmarking** [Magesan et al., PRL 106, 180504 (2011)],
    the industry-standard gate-fidelity protocol: the RB-fitted error-per-Clifford matches the
    **independently-computed** average gate infidelity of the injected T1/T2 channel to **~1 %**
    across configs (a non-circular check). The single-qubit 24-element Clifford group is built
    by closure and fingerprinted by its Pauli action (float-robust).
- **Device on the kernel**: a Bell generator (`QubitRegister → BellCircuit → BellReadout`)
  runs an n-qubit ρ through the **unchanged** `MultiRateScheduler`, with a slow RZ phase
  miscalibration (reusing `PhaseDriftOU`) drifting the fidelity tick-to-tick — the QC analog
  of QKD's drifting-AMZI QBER. Reuses `sweep()` (fidelity vs gate time) and the scenario
  system (`kind: rb`, `kind: bell_device`).

With M4, one kernel hosts four devices across three domains (QKD, QRNG, sensing, QC hardware)
with **zero kernel edits** between them — the platform thesis, demonstrated.

## Status — C1/C2 (reference-design configurator: the user-facing "design" layer)

The configurator (`qsim/configurator/`) answers *"can a user design their own device, or only
print a fixed BOM?"* — without reinventing KiCad. A high-level **`DeviceSpec`** of physically
meaningful knobs spanning the **whole Alice→fiber→Bob link** (source, modulator extinction
ratio, QRNG, encoder, distance, detector, gate rate, channels, …) drives, **consistently and
from one source of truth**:

- the **behavioural simulation** (qsim finite-key → QBER / secret-key rate), with the intrinsic
  error *derived* from the Alice modulator ER + the Bob AMZI visibility;
- the reference **whole-link hardware build** — BOM for Alice + Bob + shared infrastructure with
  a per-side cost split, and board parameters *derived* from the knobs (gate rate →
  self-differencing coax-delay = 1 gate period; detector → cryostat vs TEC; jitter budget);
- **design-rule checks** tying them together (modulator-ER security floor, jitter vs gate
  period, Alice/Bob AMZI match, BB84 QBER threshold, reach).

Turn one knob and performance, the parts list, *and* the board parameters all update together.
`configure(spec)` returns a unified report; `{InGaAs-SD, 1.25 GHz, 25 km}` reproduces the H1
hand-design (QBER 1.05 %, ~8 Mbps, 0.8 ns delay line) and prices the **whole link at ~$57k**
(Alice ~$21k + Bob ~$35k), in docs/01's $30–80k/link range. Flipping the detector to SNSPD
re-prices Bob ($35k → $329k) and re-derives the board; dropping the modulator ER below ~20 dB
flags the link infeasible. A `DeviceSpec` is shareable YAML — the **headless core a drag-and-drop
GUI will later drive**. The detailed circuit (schematic/SPICE/PCB) stays in the expert reference
design (`docs/03`, `hardware/`) + KiCad; the configurator *selects and parametrises* it.

## Status — G1 (the virtual-bench GUI)

A thin web front-end (`gui/`) over `configure()` — the first GUI layer of the "virtual quantum
bench". Flask backend + a single static vanilla-JS page (no build step; engine server-side, per
the browser/no-install/modest-hardware mission). Turn the knobs (detector, source, QRNG,
distance, gate rate, modulator ER, AMZI visibility, channels) and the page live-updates the
feasibility badge, QBER / SKR / whole-link cost, the SKR-vs-distance + BOM-cost figure, the
color-coded design rules, and the Alice/shared/Bob BOM. Verified end-to-end with headless
Chromium (swapping the detector knob updates SKR 7.9 → 26 Mbps and cost $57k → $350k live). This
is the form-based first step toward the node-editor flagship; the `DeviceSpec` data model and
the headless `configure()` core are exactly what that editor will sit on. Run: `python -m
gui.server` → `http://127.0.0.1:8000` (see `gui/README.md`).

## Install & run

```bash
pip install -e .            # or: pip install numpy scipy matplotlib pyyaml
python -m demos.m0_qber_demo        # M0 physics: QBER/SKR vs distance, phase-lock OFF vs ON
python -m demos.m0_validation       # M0 make-or-break: batched engine vs brute-force ground truth
python -m demos.m1_rusca_validation # M1 credibility: reproduce Rusca 2018 finite-key SKR figure
python -m demos.m1_engine_skr       # M1 capstone: engine-driven proven SKR, phase-lock ON vs OFF
python -m demos.m2_tuning_loop      # M2 tuning loop: sweep/optimize the SKR over mu1, p_Z
python -m demos.m3_bloch_validation # M3 backend check: Bloch integrator vs closed form
python -m demos.m3_magnetometer     # M3 generality: atomic magnetometer on the same kernel
python -m demos.m4_rb               # M4 credibility: RB error-per-Clifford vs analytic
python -m demos.m4_bell_device      # M4 multi-qubit: Bell generator on the same kernel
python -m demos.c1_configurator     # C1 configurator: one DeviceSpec -> sim + BOM together
python -m hardware.bob_gating_board.simulate          # H1 hardware: ngspice SD cancellation
python -m hardware.bob_gating_board.validate_with_qsim # H1: detector params -> QBER/SKR
jupyter notebook notebooks/M2_tuning_loop.ipynb   # M2 interactive virtual bench
pytest -q
```

Outputs (`demos/figures/`):
- `qber_skr_vs_distance.png` — classic QBER & secret-key-rate vs fiber length.
- `qber_timeseries.png` — QBER over time, phase-lock OFF vs ON (the multi-rate demo).
- `m0_validation.png` — correctness (batched vs ground truth) + scaling (cost vs pulse rate).
- `m1_rusca_validation.png` — finite-key SKR vs attenuation (cf. Rusca 2018, 4 block sizes).
- `m1_engine_skr.png` — engine-driven proven SKR vs distance, phase-lock ON vs OFF.
- `m3_bloch_validation.png` — Bloch integrator vs closed form (Larmor + T₂/T₁), max err ~1e-9.
- `m3_magnetometer.png` — magnetometer sensitivity averaging down to the projection-noise
  limit + sensitivity vs atom number (swept via the shared harness).
- `m4_rb.png` — RB survival decays `A pᵐ+B` at 3 noise levels; fitted EPC vs analytic infidelity.
- `m4_bell_device.png` — Bell fidelity wandering with slow phase drift + coherence-limited
  fidelity vs gate time.

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
- M3's δB = 1/(γ√(N·T₂·t)) is the canonical projection-noise *scaling* limit; a concrete
  readout carries an O(1) prefactor (= e for the τ=T₂ Ramsey readout modelled here). We
  validate the scaling + the exact per-scheme analytic and **report** the prefactor rather
  than pretend to hit the bare limit. The magnetometer impairments (T₁/T₂, atom number) are
  textbook-class defaults — see `qsim/profiles/rb_magnetometer.yaml` provenance.
- M4 RB needs sequence lengths scaled to the error (m up to ~ln2/r) or the `A pᵐ+B` fit is
  ill-conditioned and biases EPC high; `validate_rb` auto-scales. The RB noise is a
  gate-independent T1/T2 channel (the regime where EPC = channel infidelity exactly); SPAM and
  gate-dependent noise are out of scope. M4 uses numpy dense ρ — exact for 1–2 qubits, but it
  does **not** scale past ~6–8 qubits; QuTiP/sparse is the documented backend swap for large n.
- The M4 Bell device's RZ *phase* miscalibration degrades the exact fidelity but is invisible
  to computational-basis parity P(00)+P(11) — kept deliberately as a reminder that coherent
  phase errors need rotated-basis readout / tomography, not just population readout.

## Layout

```
qsim/core/      kernel: signals, block, graph, scheduler, backends, impairments, calibration,
                probes, sweep (tuning loop), scenario (declarative experiments)
qsim/qkd/       QKD plugin: blocks (M0 + decoy-BB84), reference builders, metrics,
                bruteforce (M0 ground truth), validation, finite_key (Rusca 2018),
                channel (decoy model), keyrate (SKR optimise/scale), scenarios
qsim/qrng/      QRNG plugin: beam-splitter QRNG built from kernel primitives (modularity)
qsim/sensing/   sensing plugin: atomic magnetometer — Bloch backend, blocks, SpinBatch,
                metrics, two-tier validation, scenario (kernel-generality proof, M3)
qsim/qchw/      QC-hardware plugin: multi-qubit density-matrix/Lindblad backend, gates+CNOT,
                Clifford group, randomized benchmarking, Bell device, two-tier validation (M4)
qsim/configurator/  reference-design configurator (C1): DeviceSpec + variant catalog + compile
                (spec -> qsim sim + BOM + board params + design rules); the headless GUI core
qsim/profiles/  calibration profiles (YAML, with provenance)
scenarios/      declarative experiment files (decoy_bb84_25km, qrng_balanced, magnetometer_rb,
                rb_transmon, bell_device_2q)
configs/        DeviceSpec files for the configurator (qkd_metro_ingaas, qkd_metro_snspd)
hardware/       QKD hardware-design track: bob_gating_board (ngspice SD front-end, schematic,
                KiCad netlist, BOM, qsim design-validation) — see docs/03
gui/            virtual-bench GUI (G1): Flask backend over configure() + vanilla-JS page
demos/          m0..m4 demos, c1_configurator
notebooks/      M0_qber_demo, M2_tuning_loop (interactive virtual bench)
tests/          test_m0, test_validation, test_finite_key, test_decoy_engine, test_sweep,
                test_qrng, test_scenario, test_sensing, test_qchw, test_configurator, test_gui
docs/           architecture+BOM (01) + kernel spec (02) + Bob gating board design (03)
```

## Roadmap

M0 kernel+QKD slice ✓ → M1 decoy-BB84 + finite-key (Rusca 2018), validated vs published
figure ✓ → M2 sweep/optimize + scenario files + QRNG plugin + Jupyter UX ✓ (calibration-
uncertainty framework + web GUI still open) → M3 sensing plugin: atomic magnetometer on the
same kernel, backend + sensitivity both validated ✓ → M4 QC-hardware plugin: multi-qubit
density-matrix/Lindblad, entangling gates, RB-validated gate fidelity ✓.

All three roadmap domains (QKD, sensing, QC hardware) + QRNG run on one unchanged kernel. The
project then forked onto the **QKD hardware-design track**: **H1** — the Bob self-differencing
gating board (ngspice-simulated cancellation, schematic + KiCad netlist + BOM, qsim
design-validation; `docs/03`) — and **C1** — the reference-design configurator tying high-level
knobs to sim + BOM + board params + design rules (`qsim/configurator/`).

Then the user-facing layers: **C1/C2** — the reference-design configurator (one DeviceSpec →
sim + whole-link BOM + board params + design rules; `qsim/configurator/`) — and **G1** — a thin
web GUI over it (`gui/`), the first step of the virtual quantum bench.

Next candidates: the node-editor (drag-and-drop) front-end on top of the configurator (the
education flagship); PCB layout (KiCad) + Bob FPGA firmware (Verilog/Verilator) for H1; the
Alice timing/laser-driver board; a QuTiP/sparse backend for larger qubit counts; and a QKD
hardware-data match for a production-grade key-rate claim.

Next for M1 to reach a *production*-grade claim: match a hardware experiment with measured
detector data (vs the current published-simulation match), and fold dead-time into the
finite-key rate rather than as a post-hoc cap.
