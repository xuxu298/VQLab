"""Tests for the multi-domain reference-design configurator (C1/C2/C3).

`configure(domain, knobs)` turns a high-level knob dict into a consistent behavioural sim +
BOM + board params + design rules, across QKD, sensing and QC-hardware domains.
"""
import os

from qsim.configurator import DeviceSpec, configure, domain_schema, list_domains


# --- registry ------------------------------------------------------------
def test_four_domains_registered():
    names = {d["name"] for d in list_domains()}
    assert {"qkd", "sensing", "qchw", "qrng"} <= names


def test_domain_schema_has_defaults_and_knobs():
    for dom in ("qkd", "sensing", "qchw", "qrng"):
        s = domain_schema(dom)
        assert s["schema"] and s["defaults"]
        # every schema knob has a default
        for k in s["schema"]:
            assert k["key"] in s["defaults"]


# --- QKD domain ----------------------------------------------------------
def test_qkd_reproduces_h1():
    r = configure("qkd", {"detector": "ingaas_sd", "gate_rate_ghz": 1.25, "distance_km": 25})
    assert abs(r.m("qber") - 1.05) < 0.2          # ~1% (Alice ER + Bob AMZI)
    assert 6e6 < r.m("skr_bps") < 11e6            # ~8 Mbps
    assert r.feasible
    assert 30_000 < r.bom_total_usd < 80_000      # docs/01 $30-80k/link
    assert {"Alice", "Bob", "shared"} <= set(r.cost_by_side)


def test_qkd_detector_swap_and_er_security():
    a = configure("qkd", {"detector": "ingaas_sd", "distance_km": 25})
    b = configure("qkd", {"detector": "snspd", "distance_km": 25})
    assert b.m("skr_bps") > a.m("skr_bps") and b.bom_total_usd > a.bom_total_usd
    assert not configure("qkd", {"detector": "ingaas_sd", "modulator_er_db": 15}).feasible


def test_qkd_gate_over_max_infeasible():
    assert not configure("qkd", {"detector": "ingaas_sd", "gate_rate_ghz": 2.5}).feasible


# --- sensing domain ------------------------------------------------------
def test_sensing_reproduces_m3_prefactor():
    # tau = T2 Ramsey readout -> sensitivity sits e (~2.72) above the projection limit (M3)
    r = configure("sensing", {"atom_number": 1e12, "T2_ms": 5, "T1_ms": 30, "tau_ms": 5})
    assert abs(r.m("asd_ratio") - 2.718) < 0.05
    assert r.feasible and r.m("sensitivity_asd") > 0


def test_sensing_more_atoms_better_sensitivity():
    few = configure("sensing", {"atom_number": 1e11, "T2_ms": 5, "tau_ms": 5})
    many = configure("sensing", {"atom_number": 1e13, "T2_ms": 5, "tau_ms": 5})
    assert many.m("sensitivity_asd") < few.m("sensitivity_asd")


def test_sensing_t2_gt_2t1_infeasible():
    assert not configure("sensing", {"T1_ms": 1, "T2_ms": 10}).feasible


# --- qc-hardware domain --------------------------------------------------
def test_qchw_reproduces_m4_numbers():
    r = configure("qchw", {"n_qubits": 2, "T1_us": 50, "T2_us": 40, "t_gate_ns": 30})
    assert abs(r.m("error_per_gate") - 3.5e-4) < 1e-4   # matches M4 analytic infidelity
    assert r.m("gate_fidelity") > 99.0
    assert r.feasible


def test_qchw_bell_only_for_two_qubits():
    one = configure("qchw", {"n_qubits": 1, "T1_us": 50, "T2_us": 70, "t_gate_ns": 40})
    two = configure("qchw", {"n_qubits": 2, "T1_us": 50, "T2_us": 70, "t_gate_ns": 40})
    keys1 = {m.key for m in one.metrics}
    keys2 = {m.key for m in two.metrics}
    assert "bell_fidelity" not in keys1 and "bell_fidelity" in keys2


def test_qchw_t2_gt_2t1_infeasible():
    assert not configure("qchw", {"T1_us": 10, "T2_us": 30, "t_gate_ns": 40}).feasible


# --- qrng domain ---------------------------------------------------------
def test_qrng_matches_mc_plugin():
    # the configurator's closed form == the Monte-Carlo qsim QRNG plugin (non-circular).
    from qsim.qrng import run_qrng
    kw = dict(mu=0.5, eta_a=0.30, eta_b=0.15, p_dark_a=1e-5, p_dark_b=1e-5)
    r = configure("qrng", {**kw, "rep_rate": 1e8})
    mc = run_qrng(n_ticks=80, pulses_per_tick=200_000, seed=1, rep_rate=1e8, **kw)
    assert abs(r.m("bias") - mc["bias"]) < 5e-3
    assert abs(r.m("min_entropy") - mc["min_entropy"]) < 5e-3
    assert abs(r.m("sift_efficiency") - mc["sift_efficiency"]) < 5e-3


def test_qrng_balanced_is_unbiased_full_entropy():
    r = configure("qrng", {"eta_a": 0.20, "eta_b": 0.20, "p_dark_a": 1e-5, "p_dark_b": 1e-5})
    assert r.m("bias") < 1e-9 and abs(r.m("min_entropy") - 1.0) < 1e-9
    assert r.feasible and r.m("extractable_rate") > 0


def test_qrng_mismatch_lowers_min_entropy():
    bal = configure("qrng", {"eta_a": 0.20, "eta_b": 0.20})
    mis = configure("qrng", {"eta_a": 0.40, "eta_b": 0.05})
    assert mis.m("min_entropy") < bal.m("min_entropy")
    assert mis.m("bias") > bal.m("bias")


def test_qrng_severe_bias_infeasible():
    # extreme efficiency asymmetry drives H_min below the 0.5 bit practical floor -> FAIL
    assert not configure("qrng", {"eta_a": 0.9, "eta_b": 0.05, "mu": 1.5}).feasible


# --- shipped QKD config files (DeviceSpec YAML -> qkd knobs) --------------
def test_shipped_config_files_configure():
    from dataclasses import asdict
    root = os.path.join(os.path.dirname(__file__), "..", "configs")
    for fn in ("qkd_metro_ingaas.yaml", "qkd_metro_snspd.yaml"):
        spec = DeviceSpec.from_yaml(os.path.join(root, fn))
        r = configure("qkd", asdict(spec))
        assert r.feasible and r.m("skr_bps") > 0
