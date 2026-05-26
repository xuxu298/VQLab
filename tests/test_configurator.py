"""Tests for the reference-design configurator (C1).

The configurator turns a high-level DeviceSpec into a consistent behavioural sim + BOM + board
parameters + design rules. These check the H1 reproduction, knob-propagation, BOM scaling, and
design-rule firing.
"""
import os

from qsim.configurator import DeviceSpec, configure


def test_ingaas_spec_reproduces_h1():
    """{InGaAs-SD, 1.25 GHz, 25 km, 2 ch} must reproduce the H1 hand-design numbers."""
    r = configure(DeviceSpec(detector="ingaas_sd", gate_rate_hz=1.25e9, distance_km=25.0))
    assert abs(r.qber - 0.01) < 0.002                 # ~1% (misalignment-dominated)
    assert 6e6 < r.skr_bps < 11e6                     # ~8 Mbps
    assert r.feasible
    # derived board parameter: SD delay line = one gate period
    assert abs(r.board_params["sd_delay_line_ns"] - 0.80) < 0.01


def test_one_knob_propagates_to_sim_and_bom():
    base = DeviceSpec(detector="ingaas_sd", distance_km=25.0)
    a = configure(base)
    b = configure(base.replace(detector="snspd"))
    # SNSPD: higher SKR (better PDE) AND higher BOM cost AND different cooling
    assert b.skr_bps > a.skr_bps
    assert b.bom_total_usd > a.bom_total_usd
    assert "cryostat" in b.board_params["cooling"]
    assert "TEC" in a.board_params["cooling"]


def test_bom_scales_with_channels():
    two = configure(DeviceSpec(detector="ingaas_sd", n_channels=2))
    four = configure(DeviceSpec(detector="ingaas_sd", n_channels=4))
    qty2 = next(i.qty for i in two.bom if i.ref == "D")
    qty4 = next(i.qty for i in four.bom if i.ref == "D")
    assert qty4 == 2 * qty2 == 4
    assert four.bom_total_usd > two.bom_total_usd


def test_gate_over_max_is_infeasible():
    r = configure(DeviceSpec(detector="ingaas_sd", gate_rate_hz=2.5e9))  # > 1.25 GHz max
    assert not r.feasible
    assert any(level == "FAIL" for level, _ in r.rules)


def test_too_far_for_ingaas_has_no_key():
    r = configure(DeviceSpec(detector="ingaas_sd", distance_km=200.0))
    assert r.skr_bps == 0.0
    assert not r.feasible


def test_snspd_reaches_further_than_ingaas():
    far = DeviceSpec(distance_km=120.0)
    assert configure(far.replace(detector="snspd")).skr_bps > 0.0


def test_spec_yaml_roundtrip(tmp_path):
    s = DeviceSpec(name="rt", detector="snspd", n_channels=4, distance_km=33.0)
    p = tmp_path / "spec.yaml"
    s.to_yaml(p)
    s2 = DeviceSpec.from_yaml(p)
    assert s2.detector == "snspd" and s2.n_channels == 4 and s2.distance_km == 33.0


def test_shipped_config_files_load_and_configure():
    root = os.path.join(os.path.dirname(__file__), "..", "configs")
    for fn in ("qkd_metro_ingaas.yaml", "qkd_metro_snspd.yaml"):
        r = configure(DeviceSpec.from_yaml(os.path.join(root, fn)))
        assert r.feasible
        assert r.skr_bps > 0.0


# --- C2: full Alice+Bob link --------------------------------------------
def test_full_link_bom_spans_alice_shared_bob():
    r = configure(DeviceSpec(detector="ingaas_sd", distance_km=25.0))
    sides = {it.side for it in r.bom}
    assert {"Alice", "Bob", "shared"} <= sides
    # Alice carries the source + modulator (A1, A2 present)
    refs = {it.ref for it in r.bom}
    assert {"A1", "A2", "AE5"} <= refs            # laser, intensity mod, QRNG
    assert abs(sum(r.cost_by_side.values()) - r.bom_total_usd) < 1e-6


def test_total_link_cost_in_docs_range():
    # docs/01 §8: Phase-1 InGaAs ~ $30-80k per link
    r = configure(DeviceSpec(detector="ingaas_sd", distance_km=25.0))
    assert 30_000 < r.bom_total_usd < 80_000
    assert r.cost_by_side["Alice"] > 0 and r.cost_by_side["Bob"] > 0


def test_modulator_er_raises_qber():
    hi = configure(DeviceSpec(detector="ingaas_sd", modulator_er_db=35))
    lo = configure(DeviceSpec(detector="ingaas_sd", modulator_er_db=22))
    assert lo.e_d > hi.e_d                        # finite ER adds state-prep error
    assert lo.qber > hi.qber


def test_low_extinction_ratio_is_infeasible():
    r = configure(DeviceSpec(detector="ingaas_sd", modulator_er_db=15))
    assert not r.feasible
    assert any(level == "FAIL" and "ER" in msg for level, msg in r.rules)


def test_jitter_budget_rule_fires():
    r = configure(DeviceSpec(detector="ingaas_sd", gate_rate_hz=1.25e9, source_jitter_ps=300))
    assert any(level == "WARN" and "jitter" in msg for level, msg in r.rules)
