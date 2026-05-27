"""Close the hardware<->sim loop for the Bob FPGA firmware (H2).

The firmware's afterpulse gate-veto length is not a free parameter: it is the SAME detector dead
time qsim uses in its finite-key model (`qsim.configurator.catalog.DETECTORS`). This script:

  1. reads the H1 detector's tau_dead + gate rate from qsim,
  2. derives the firmware knob   veto_cycles = round(tau_dead * gate_rate),
  3. checks the firmware-enforced dead time matches tau_dead to within one gate period,
  4. co-simulates: drives the Verilator firmware with a Bernoulli click stream and checks the
     measured accepted rate follows the non-paralyzable dead-time law m = r / (1 + r * veto),
     i.e. the firmware reproduces the very dead-time throttling qsim assumes.

Run:  python hardware/bob_fpga/validate_with_qsim.py     (needs verilator; like H1's ngspice loop)
"""
from __future__ import annotations

import sys

from qsim.configurator.catalog import DETECTORS

from . import sim


def main() -> int:
    det = DETECTORS["ingaas_sd"]
    gate_rate = det.max_gate_rate_hz          # H1 Phase-1 operating point (1.25 GHz)
    t_gate = 1.0 / gate_rate
    veto = round(det.tau_dead * gate_rate)    # derive the firmware knob from the sim's dead time
    enforced_dead = veto * t_gate

    print("Bob FPGA firmware <-> qsim detector model")
    print(f"  detector            : {det.label}")
    print(f"  gate rate           : {gate_rate/1e9:.3f} GHz   (gate period {t_gate*1e12:.0f} ps)")
    print(f"  qsim tau_dead       : {det.tau_dead*1e9:.2f} ns")
    print(f"  -> veto_cycles      : {veto} gates")
    print(f"  enforced dead time  : {enforced_dead*1e9:.2f} ns  (= {veto} x {t_gate*1e12:.0f} ps)")
    max_rate = gate_rate / (veto + 1)
    print(f"  saturated max rate  : {max_rate/1e6:.1f} Mcps  (gate_rate/(veto+1))")

    ok = True

    # (3) the firmware dead time must match the sim's tau_dead to within the gate quantization
    if abs(enforced_dead - det.tau_dead) <= t_gate + 1e-15:
        print(f"\n  [ ok ] enforced dead time {enforced_dead*1e9:.2f} ns matches qsim tau_dead "
              f"{det.tau_dead*1e9:.2f} ns within one gate ({t_gate*1e12:.0f} ps)")
    else:
        ok = False
        print(f"\n  [FAIL] dead-time mismatch > one gate period")

    if not sim.have_verilator():
        print("\n  (verilator not installed — skipping the co-simulation; install to run it)")
        return 0 if ok else 1

    # (4) co-simulate: the measured accepted rate must follow the non-paralyzable dead-time law.
    print("\n  co-simulating the firmware on a random comparator stream:")
    print(f"  {'p_click/gate':>12} {'measured m':>12} {'model r/(1+rD)':>16} {'ghost%':>8} {'afterp%':>8}")
    for p in (0.02, 0.05, 0.10, 0.20):
        st = sim.run_stream(veto=veto, pclick=p, gates=1_000_000, seed=1)
        g = st["gates"]
        m = st["n_accepted"] / g                      # measured accepted fraction per gate
        r = st["n_in"] / g                            # actual input click fraction (~p)
        model = r / (1.0 + r * veto)                  # non-paralyzable dead-time prediction
        rel = abs(m - model) / model
        ghost_pct = 100.0 * st["n_ghost"] / st["n_in"]
        ap_pct = 100.0 * st["n_afterpulse"] / st["n_in"]
        flag = "ok" if rel < 0.02 else "FAIL"
        if rel >= 0.02:
            ok = False
        print(f"  {p:>12.2f} {m:>12.5f} {model:>16.5f} {ghost_pct:>7.2f}% {ap_pct:>7.2f}%  [{flag}] "
              f"({rel*100:.2f}% off)")

    print(f"\n  => {'LOOP CLOSED' if ok else 'MISMATCH'}: firmware veto derived from qsim tau_dead, "
          f"and its measured throttling follows the dead-time law qsim assumes.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
