"""System-integration timing-budget tests (H1+H2+H3+finite-key assembled into one link)."""
import math

from hardware.system_integration.timing_budget import (BUDGET_FRACTION, build_budget,
                                                        dispersion_limited_reach_km, dispersion_ps,
                                                        timing_efficiency)

GATE_HZ = 1.25e9
SRC, DET = 20.0, 90.0   # gain-switched DFB / InGaAs-SD jitter (catalog)


def _budget(L):
    return build_budget(L, GATE_HZ, source_jitter_ps=SRC, detector_jitter_ps=DET)


def test_rss_is_quadrature_sum():
    b = _budget(25)
    expected = math.sqrt(sum(c.ps ** 2 for c in b.contributions))
    assert abs(b.total_ps - expected) < 1e-9


def test_fixed_floor_excludes_dispersion():
    b = _budget(25)
    expected = math.sqrt(SRC ** 2 + DET ** 2 + 15.0 ** 2 + 10.0 ** 2)  # clock + TDC defaults
    assert abs(b.fixed_ps - expected) < 1e-9
    # the fixed floor is distance-independent
    assert abs(_budget(10).fixed_ps - _budget(100).fixed_ps) < 1e-9


def test_dispersion_grows_linearly_from_zero():
    assert dispersion_ps(0) == 0.0
    assert dispersion_ps(50) > dispersion_ps(25) > dispersion_ps(10) > 0
    assert abs(dispersion_ps(50) - 2 * dispersion_ps(25)) < 1e-9   # linear in L


def test_gate_period_and_budget():
    b = _budget(25)
    assert abs(b.gate_period_ps - 800.0) < 1e-6        # 1/1.25 GHz
    assert abs(b.budget_ps - 200.0) < 1e-6             # 25% rule


def test_phase1_within_budget_long_haul_over():
    assert _budget(25).within_budget and _budget(25).margin < 1.0
    assert not _budget(100).within_budget and _budget(100).margin > 1.0


def test_total_jitter_increases_with_distance():
    assert _budget(100).total_ps > _budget(50).total_ps > _budget(25).total_ps


def test_dispersion_limited_reach_consistent():
    reach = dispersion_limited_reach_km(GATE_HZ, _budget(25).fixed_ps)
    assert 50 < reach < 90                              # ~69 km for this config
    # at the reach, total timing == the budget (definition)
    b = _budget(reach)
    assert abs(b.total_ps - b.budget_ps) < 1.0


def test_timing_efficiency_bounds():
    assert timing_efficiency(50, 800) > 0.999          # tiny jitter vs slot -> ~1
    assert timing_efficiency(2000, 800) < 0.6          # huge jitter -> rolls off
    assert timing_efficiency(0, 800) == 1.0


def test_integrate_analyze_closes_phase1():
    from hardware.system_integration.integrate import PHASE1_KM, analyze
    a = analyze([25, 100])
    row25 = next(r for r in a["rows"] if r["km"] == 25)
    assert row25["skr"] > 0 and row25["qber"] < 11.0   # feasible Phase-1 (qber in %)
    assert row25["margin"] < 1.0                        # within timing budget
    assert PHASE1_KM < a["timing_reach_km"]             # loss bites before timing at metro
