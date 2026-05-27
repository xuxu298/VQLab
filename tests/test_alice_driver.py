"""Tests for the Alice gain-switch laser driver (H3) — runs ngspice + the laser model.

Skipped where ngspice is absent, so `pytest -q` stays green on a bare environment.
"""
import shutil

import pytest

pytestmark = pytest.mark.skipif(shutil.which("ngspice") is None,
                                reason="ngspice not installed")

from hardware.alice_laser_driver import simulate, validate_with_qsim   # noqa: E402


def test_gainswitch_pulse_is_short_and_phase_random():
    d = simulate.analyze()
    assert d["fwhm_ps"] < 500                       # decoy-BB84 wants << gate period
    assert d["fwhm_ps"] < 0.25 * (1e3 / 1.25)       # fits inside the 800 ps slot, no ISI
    assert d["bias"] * 1e3 < d["ith_ma"]            # biased BELOW threshold (gain switching)
    assert d["i_peak_ma"] > d["ith_ma"]             # the pulse drives well above threshold
    assert d["on_off"] > 1e3                        # field decays between pulses -> random phase


def test_qsim_loop_closes():
    assert validate_with_qsim.main() == 0
