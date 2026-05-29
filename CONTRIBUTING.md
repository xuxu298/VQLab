# Contributing to VQLab

Thanks for your interest in VQLab — the open-source virtual quantum bench.
This document explains **what VQLab is (and isn't)**, how to get a working
dev setup, and what kinds of contributions are most useful.

## What VQLab is — and what it isn't

VQLab is a **reference + teaching tool** for quantum-device R&D:

- ✅ A validated multi-rate **simulator** (QKD, QRNG, atomic magnetometer,
  few-qubit QC hardware), with each device matched against an independent
  published result (Rusca 2018 finite-key; Budker–Romalis projection-noise
  limit; randomized benchmarking).
- ✅ A **reference-design configurator + GUI** that turns high-level knobs
  into a behavioural sim + BOM + board parameters + design-rule checks.
- ✅ Reference-grade **hardware artifacts** (ngspice front-end models,
  headless KiCad netlists/layouts, Verilog firmware via Verilator) so the
  design–sim–schematic–layout chain is *visible end-to-end*.

VQLab is **not** a production product:

- ❌ It is **not** validated against measured field hardware. The reference
  designs reproduce *published-simulation* results; calibration values,
  detector parameters, and BOM prices are datasheet/paper-class defaults.
- ❌ It is **not** a deployable QKD device. Production-grade firmware
  hardening, manufacturing process, RF trim, real metro-link integration,
  and certification are deliberately out of scope here.
- ❌ It carries **no warranty for any operational use** (see [`LICENSE`](LICENSE)).

If you fork VQLab to build a production device, you own all the execution
work that VQLab doesn't cover — calibration, manufacturing, field validation,
certification.

## Getting set up

```bash
git clone https://github.com/xuxu298/VQLab.git
cd VQLab
python -m venv .venv && source .venv/bin/activate
pip install -e ".[gui]"          # core + GUI; pytest is in core deps
python -m qsim                   # 4-domain self-check (~1 s)
python -m qsim gui               # bench at http://127.0.0.1:8000
pytest -q                        # the validation suite (~1 min, 95+ tests)
```

Optional extras:
- `pip install -e ".[dev]"` — adds Playwright (only needed for `gui/screenshot.py`)
- `pip install -e ".[quantum]"` — adds QuTiP (only for large-n QC hardware swap-in)

External tools (only some tests require them, the suite gracefully skips
the corresponding tests if missing):
- **ngspice** — Alice laser driver + Bob gating-board SPICE
- **verilator** — Bob FPGA firmware simulation
- **kicad** (pcbnew Python bindings) — headless PCB layout (`hardware/bob_gating_board/layout.py`)

## What kinds of contributions are most useful

**High-value, welcomed:**

1. **Validation against new published results** — additional figures we can
   reproduce (more decoy-state papers, different sensor protocols,
   alternative QC noise models). Each one strengthens the validation evidence.
2. **Documentation, tutorials, teaching material** — VQLab is built for
   education (universities, labs, students); clear tutorials with
   well-annotated scenarios are gold.
3. **New domain plugins** — the kernel is intentionally
   domain-general; a new device (NV-center magnetometer, ion-trap QC, MDI
   QKD, …) tests that claim and broadens reach. See `qsim/sensing/` and
   `qsim/qchw/` for the pattern.
4. **Reference designs for the configurator** — alternative detectors,
   sources, modulators with BOM cost + design-rule entries.
5. **Bug fixes** — anything where a documented behavior doesn't match
   what the code does.
6. **Honesty-notes additions** — known limitations, systematic effects,
   regimes where the model breaks down. We'd rather know than hide them.

**Out of scope here** (please don't open PRs for these):

- Production firmware hardening for a specific device deployment
- Vendor-specific RF trim values or supplier-specific BOM line items
- Calibration procedures tied to specific measured hardware
- Marketing/branding changes (the brand is a separate concern)

## Submitting a change

1. Open an issue first for anything non-trivial — saves both of us time
   if the direction needs discussion.
2. Fork → branch → PR against `main`. Squash-merge is fine; rebase
   contributions are appreciated but not required.
3. **Tests must pass** (`pytest -q`). If a test should be added for your
   change and isn't obvious how, mention it in the PR — we'll work it out.
4. **Honest claims only**: if you add a result, it must be validated
   (against a published reference, against a closed-form, or against the
   bruteforce ground-truth, depending on context). Unvalidated numbers
   are not merged.
5. Code style: follow what's already there. No linter is enforced; we
   value readability and physics correctness over formatting religion.

## License

All contributions are accepted under the [MIT License](LICENSE), the same
license VQLab is published under. By submitting a PR you confirm that you
have the right to license the contribution under MIT.

## Questions

- Open a GitHub issue (preferred — public, others benefit from the answer)
- Email: support@vradar.io
