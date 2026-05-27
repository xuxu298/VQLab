# Alice gain-switch laser-driver / timing board (H3)

The transmitter front-end of the QKD link (docs/01 Alice; docs/03 §7 step 5). It produces the
short, phase-randomised optical pulses decoy-BB84 needs, at the 1.25 GHz system rep rate.

## Why gain switching

A fast current pulse drives the DFB laser from **below** threshold to well above it for ~100 ps.
The laser then emits a single short relaxation-oscillation spike (~tens of ps) — and because each
pulse builds up from **spontaneous emission**, its optical phase is random shot-to-shot. That kills
inter-pulse coherence **for free**, satisfying a decoy-BB84 security requirement with no active
phase randomiser. Between pulses the bias sits below threshold so the field fully decays and the
next pulse is independent.

## What the simulation shows

| Quantity | Result |
|---|---|
| Threshold current Ith | 12.0 mA (from the laser model) |
| DC bias / peak injection | 8 mA (below threshold) / ~68 mA |
| **Optical pulse FWHM** | **~21 ps**  (≪ 500 ps; ≪ the 800 ps gate slot) |
| Turn-on delay | ~170 ps |
| Driver-noise jitter floor | ~0.2 ps (the physical floor is spontaneous-emission turn-on jitter, a few ps) |
| On/off ratio between pulses | ~4×10⁴  → field resets → random phase |

## Run it

```bash
sudo apt install ngspice                                  # one-time
python3 -m hardware.alice_laser_driver.simulate           # ngspice -> laser model -> figure
python3 -m hardware.alice_laser_driver.validate_with_qsim # close the hardware<->sim loop
```

- **`alice_driver.cir`** — the ELECTRICAL half in ngspice: a 50 Ω driver pulse, AC-coupled through
  a bias-tee onto a DC bias current, into a laser-diode load (junction + series R + junction C +
  bond-wire L). It outputs the injection-current waveform.
- **`simulate.py`** — runs ngspice, then integrates a **two-rate-equation single-mode laser model**
  (carrier number N, photon number S) driven by that current to get the OPTICAL pulse, and measures
  the width, turn-on delay, driver-noise jitter, and the inter-pulse on/off ratio. Figure:
  `demos/figures/h3_gainswitch.png`.
- **`validate_with_qsim.py`** — feeds the pulse's timing into the qsim configurator (`source_jitter_ps`,
  the gain-switched DFB source) and confirms the Phase-1 link is feasible: the pulse fits one slot,
  the total timing jitter (≈92 ps) is under the 0.25×period budget (200 ps), and QBER ~1 % / SKR
  ~7.9 Mbps. Same hardware↔sim closure as Bob's H1 (ngspice) and H2 (Verilator) loops.

`tests/test_alice_driver.py` runs both under `pytest` (auto-skipped without ngspice).

## Next

Bias-point / pulse-amplitude trim against the chosen DFB datasheet; the comb/SRD or iC-HG-class
driver IC selection + its own SPICE model; clock distribution from the OCXO + low-jitter PLL shared
with Bob's gate generator (the two boards must be co-timed). The two-rate-equation parameters here
are representative of a 1550 nm DFB; tighten them to the chosen part for the fab revision.
