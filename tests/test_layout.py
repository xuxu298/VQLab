"""Tests for the programmatic KiCad PCB layout (hardware/bob_gating_board/layout.py).

Skipped where the KiCad `pcbnew` Python module is absent, so `pytest -q` stays green on a bare
environment (install kicad to exercise them). Guards the two things the layout must get right for
this board: the 50 ohm microstrip width and the self-differencing delay = exactly one gate period.
"""
import pytest

pytest.importorskip("pcbnew")
from hardware.bob_gating_board import layout   # noqa: E402  (after importorskip)


def test_50ohm_microstrip_width_reasonable():
    assert 0.30 < layout.RF_W_MM < 0.50          # FR4 microstrip, h=0.2 mm -> ~0.39 mm


def test_delay_arm_is_one_gate_period():
    _board, meander_mm, direct_mm, _pour = layout.build()
    delay_ns = (meander_mm - direct_mm) / layout.V_EFF / 1e3 * 1e9
    assert abs(delay_ns - layout.GATE_PERIOD_S * 1e9) < 0.01   # arm_B - arm_A within 10 ps of 0.8 ns


def test_board_structure():
    board, *_ = layout.build()
    assert board.GetCopperLayerCount() == 4
    assert len(board.GetFootprints()) == 14                    # 15 netlist parts minus the meandered DL1
    assert len(list(board.GetTracks())) > 20                   # the serpentine alone is many segments
    for name in ("ARM_B", "ARM_A_DIRECT", "SD_OUT", "GND"):
        assert board.FindNet(name) is not None
