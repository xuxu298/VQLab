"""M0 sanity tests — the physics has the right shape and the kernel wiring holds."""
import numpy as np
import pytest

from qsim.core.graph import DeviceGraph
from qsim.core.block import Block
from qsim.core.signals import SignalType
from qsim.qkd.metrics import binary_entropy, secret_fraction
from qsim.qkd.reference import build_bb84_slice


def _run(length_km, locked=True, pulses=200_000, ticks=20, seed=1):
    rng = np.random.default_rng(seed)
    _g, sched, det, _amzi = build_bb84_slice(length_km=length_km, locked=locked)
    recs = sched.run(n_ticks=ticks, dt_slow=1e-3, pulses_per_tick=pulses, rng=rng)
    return recs[-1]


def test_binary_entropy_and_threshold():
    assert binary_entropy(0.0) == pytest.approx(0.0, abs=1e-9)
    assert binary_entropy(0.5) == pytest.approx(1.0, abs=1e-9)
    assert secret_fraction(0.01) > 0.5          # low error -> healthy key
    assert secret_fraction(0.12) == 0.0          # past ~11% -> no secret key


def test_graph_type_check_rejects_mismatch():
    g = DeviceGraph()
    a, b = Block("a"), Block("b")
    a.ports_out = {"o": SignalType.OPTICAL}
    b.ports_in = {"i": SignalType.ELECTRICAL}
    g.add(a)
    g.add(b)
    with pytest.raises(TypeError):
        g.connect("a", "o", "b", "i")


def test_near_qber_low():
    # 25 km gives ~30k sifted clicks -> robust estimate; QBER is intrinsic+afterpulse, a few %.
    assert _run(25.0, pulses=200_000, ticks=20)["qber"] < 0.04


def test_qber_increases_with_distance():
    # Need enough pulses that 125 km has ~1.6k clicks; the far tail (150km+) has too few
    # clicks per run to assert on (see demos diagnostic) -- that's statistics, not physics.
    q25 = _run(25.0, pulses=400_000, ticks=25)["qber"]
    q125 = _run(125.0, pulses=400_000, ticks=25)["qber"]
    assert q25 < 0.04
    assert q125 > q25 + 0.01      # dark counts start to overtake the attenuated signal
    assert q125 > 0.035


def test_skr_falls_orders_of_magnitude_with_distance():
    s25 = _run(25.0, pulses=200_000, ticks=20)["skr"]
    s125 = _run(125.0, pulses=200_000, ticks=20)["skr"]
    s175 = _run(175.0, pulses=200_000, ticks=20)["skr"]
    assert s25 > 0
    assert s25 > 50 * s125        # SKR spans orders of magnitude metro -> long range
    assert s175 < s25 / 100        # far end collapses past the ~11% QBER threshold


def test_phase_lock_reduces_qber():
    # Unlocked drift should inflate mean QBER vs locked at the same distance.
    rng = np.random.default_rng(7)
    _g, s_off, d_off, _ = build_bb84_slice(length_km=25.0, locked=False)
    off = s_off.run(n_ticks=500, dt_slow=1e-3, pulses_per_tick=30_000, rng=rng)
    rng = np.random.default_rng(7)
    _g, s_on, d_on, _ = build_bb84_slice(length_km=25.0, locked=True)
    on = s_on.run(n_ticks=500, dt_slow=1e-3, pulses_per_tick=30_000, rng=rng)
    mean_off = np.mean([r["inst_qber"] for r in off])
    mean_on = np.mean([r["inst_qber"] for r in on])
    assert mean_on < mean_off
