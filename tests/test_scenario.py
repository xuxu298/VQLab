"""Tests for declarative scenario files (qsim/core/scenario.py + plugin runners)."""
from pathlib import Path

import pytest

import qsim
from qsim.core.scenario import available_kinds, run_scenario

SCEN = Path(__file__).resolve().parents[1] / "scenarios"


def test_plugins_register_kinds():
    kinds = qsim.load_scenario_plugins()
    assert {"decoy_bb84", "bb84_slice", "qrng"} <= set(kinds)
    assert set(kinds) == set(available_kinds())


def test_unknown_kind_raises():
    with pytest.raises(KeyError):
        run_scenario({"kind": "does_not_exist"})


def test_decoy_bb84_scenario_from_yaml():
    qsim.load_scenario_plugins()
    out = run_scenario(SCEN / "decoy_bb84_25km.yaml")
    assert out["feasible"] and out["skr_hz"] > 0
    assert 0.0 < out["qber_Z"] < 0.05
    assert 0.0 < out["l_over_nZ"] < 1.0


def test_qrng_scenario_from_yaml():
    qsim.load_scenario_plugins()
    out = run_scenario(SCEN / "qrng_balanced.yaml")
    assert out["min_entropy"] > 0.99
    assert out["bias"] < 0.01


def test_scenario_accepts_dict_inline():
    qsim.load_scenario_plugins()
    out = run_scenario({
        "kind": "qrng",
        "builder_args": {"eta_a": 0.25, "eta_b": 0.15},
        "run": {"n_ticks": 50, "pulses_per_tick": 100000, "seed": 3},
    })
    assert out["bias"] > 0.05            # mismatch -> biased, as configured
