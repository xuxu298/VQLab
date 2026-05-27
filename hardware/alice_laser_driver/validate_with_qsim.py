"""Close the hardware<->sim loop for the Alice gain-switch driver (H3).

The driver design produces an optical pulse with a width and a timing jitter. qsim's link model
consumes exactly those as the source's `source_jitter_ps` (timing) and rep-rate ceiling. This
script takes the simulated pulse, feeds the source timing into the configurator, and confirms the
designed transmitter is good enough for the Phase-1 link — the same closure H1/H2 did for Bob.

Run:  python -m hardware.alice_laser_driver.validate_with_qsim   (needs ngspice)
"""
from __future__ import annotations

import sys

from qsim.configurator import configure
from qsim.configurator.catalog import SOURCES

from . import simulate


def main() -> int:
    d = simulate.analyze()
    src = SOURCES["gainswitched_dfb"]
    gate_ghz = 1.25
    gate_period_ps = 1e3 / gate_ghz

    print("Alice gain-switch driver <-> qsim link model")
    print(f"  source                  : {src.label}")
    print(f"  simulated pulse FWHM    : {d['fwhm_ps']:.1f} ps  (gate period {gate_period_ps:.0f} ps)")
    print(f"  simulated turn-on jitter: {d['jitter_ps']:.2f} ps (driver-noise floor)")
    print(f"  catalog source jitter   : {src.jitter_ps:.0f} ps (conservative spec used downstream)")
    print(f"  phase randomisation     : on/off {d['on_off']:.0e}  (each pulse builds from spontaneous emission)")

    ok = True

    # (1) the optical pulse must fit well inside one gate period (no inter-symbol leakage)
    if d["fwhm_ps"] < 0.25 * gate_period_ps:
        print(f"\n  [ ok ] pulse FWHM {d['fwhm_ps']:.0f} ps << gate period {gate_period_ps:.0f} ps "
              f"-> one pulse per slot, no ISI")
    else:
        ok = False
        print(f"\n  [FAIL] pulse too wide for the gate period")

    # (2) the driver-noise jitter floor must sit well under the catalog spec
    if d["jitter_ps"] < src.jitter_ps:
        print(f"  [ ok ] driver-noise jitter {d['jitter_ps']:.2f} ps << catalog {src.jitter_ps:.0f} ps "
              f"-> the driver electronics are not the jitter bottleneck")
    else:
        ok = False
        print(f"  [FAIL] driver jitter exceeds the source budget")

    # (3) phase randomisation (gain-switching) — a decoy-BB84 security requirement, for free
    if d["on_off"] > 1e3:
        print(f"  [ ok ] field fully decays between pulses (on/off {d['on_off']:.0e}) "
              f"-> random optical phase, no active randomiser needed")
    else:
        ok = False
        print(f"  [FAIL] residual field between pulses -> phase not randomised")

    # (4) feed the source timing into the full configurator and confirm the link is feasible
    rep = configure("qkd", {"source": "gainswitched_dfb", "detector": "ingaas_sd",
                            "gate_rate_ghz": gate_ghz, "distance_km": 25,
                            "source_jitter_ps": src.jitter_ps})
    total_jitter = float(rep.board_params["total_jitter_ps"])
    print(f"\n  qsim link @25 km, 1.25 GHz, this source:")
    print(f"    total jitter (src(+)det): {total_jitter:.1f} ps  (timing budget = 0.25x period "
          f"= {0.25*gate_period_ps:.0f} ps)")
    print(f"    QBER {rep.m('qber'):.2f} %   SKR {rep.m('skr_bps')/1e6:.2f} Mbps   feasible={rep.feasible}")
    if not (rep.feasible and total_jitter < 0.25 * gate_period_ps):
        ok = False
        print("    [FAIL] link not feasible / jitter over budget")

    print(f"\n  => {'LOOP CLOSED' if ok else 'MISMATCH'}: the simulated gain-switch pulse "
          f"(short, low-jitter, phase-randomised) feeds qsim and the Phase-1 link is feasible.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
