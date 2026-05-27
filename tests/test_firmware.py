"""Tests for the Bob FPGA firmware (H2) — runs the Verilator simulation.

Skipped automatically where Verilator is not installed, so `pytest -q` stays green on a bare
environment; install verilator (apt) to exercise them. Mirrors the project's hardware<->sim
discipline: the RTL is checked behaviourally, then tied back to the qsim detector model.
"""
import pytest

from hardware.bob_fpga import sim

pytestmark = pytest.mark.skipif(not sim.have_verilator(),
                                reason="verilator not installed (apt install verilator)")


def test_firmware_scenarios_pass():
    rc, out = sim.build_and_run()
    assert rc == 0, out
    assert "0 failed" in out                      # the C++ testbench's own summary


def test_firmware_enforces_qsim_dead_time():
    # veto length is derived from the qsim detector's tau_dead; the firmware's measured throttling
    # must follow the non-paralyzable dead-time law m = r/(1 + r*veto) qsim assumes.
    from qsim.configurator.catalog import DETECTORS
    det = DETECTORS["ingaas_sd"]
    veto = round(det.tau_dead * det.max_gate_rate_hz)
    assert veto == 4
    st = sim.run_stream(veto=veto, pclick=0.05, gates=200_000, seed=2)
    assert st["n_accepted"] + st["n_ghost"] + st["n_afterpulse"] == st["n_in"]   # conservation
    r = st["n_in"] / st["gates"]
    m = st["n_accepted"] / st["gates"]
    model = r / (1.0 + r * veto)
    assert abs(m - model) / model < 0.02          # within 2% of the dead-time law
