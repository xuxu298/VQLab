"""Tests for the sensing plugin (M3) — the kernel-generality milestone.

These cover the two-tier validation evidence (backend integrator vs closed form;
device sensitivity vs the Budker-Romalis projection-noise limit), the device running on the
unchanged kernel, the typed-port checks for the non-QKD signal types, and reuse of the
domain-agnostic sweep harness.
"""
import numpy as np

from qsim.core.graph import DeviceGraph
from qsim.core.signals import SignalType
from qsim.core.sweep import sweep
from qsim.sensing.backend import RB87_GAMMA, SpinEnsembleBackend
from qsim.sensing.blocks import AmbientField, AtomicVaporCell, ProbeReadout
from qsim.sensing.reference import build_magnetometer, run_magnetometer
from qsim.sensing.validation import (
    projection_noise_limit,
    validate_bloch,
    validate_sensitivity,
)


# --- Tier 1: backend correctness -----------------------------------------
def test_integrator_matches_analytic_bloch():
    """RK4 Bloch integration must track the closed form (Larmor + T2 decay + T1)."""
    c = validate_bloch()
    assert c.max_abs_err < 1e-4


def test_projection_noise_scales_as_inverse_sqrt_n():
    be = SpinEnsembleBackend()
    assert be.projection_noise_std(1e6) == 1.0 / np.sqrt(1e6)
    assert np.isclose(be.projection_noise_std(4e6), 0.5 * be.projection_noise_std(1e6))


# --- Tier 2: sensitivity vs the published limit --------------------------
def test_sensitivity_matches_analytic_and_projection_limit():
    s = validate_sensitivity(N=1e6, T2=1e-3, t=1.0, n_trials=4000, seed=0)
    # MC std matches the exact per-scheme analytic to within Monte-Carlo error
    assert s.rel_err < 0.05
    # at tau = T2 the honest O(1) prefactor over the Budker-Romalis limit is e
    assert abs(s.prefactor - np.e) < 0.1


def test_sensitivity_follows_budker_romalis_scaling():
    base = validate_sensitivity(N=1e6, T2=1e-3, t=1.0, n_trials=3000, seed=3)
    n4 = validate_sensitivity(N=4e6, T2=1e-3, t=1.0, n_trials=3000, seed=3)
    t4 = validate_sensitivity(N=1e6, T2=1e-3, t=4.0, n_trials=3000, seed=3)
    # dB ~ 1/sqrt(N*t): quadrupling N or t halves the sensitivity floor
    assert abs(base.emp_sensitivity / n4.emp_sensitivity - 2.0) < 0.15
    assert abs(base.emp_sensitivity / t4.emp_sensitivity - 2.0) < 0.15


def test_projection_limit_formula():
    g = RB87_GAMMA
    assert np.isclose(projection_noise_limit(N=1e6, T2=1e-3, t=1.0, gamma=g),
                      1.0 / (g * np.sqrt(1e6 * 1e-3 * 1.0)))


# --- the device on the kernel --------------------------------------------
def test_magnetometer_runs_on_kernel_and_recovers_field():
    r = run_magnetometer(n_ticks=100, cycles_per_tick=4000, B_dc=1e-9, seed=0)
    # recovers the DC test field to well within the per-cycle noise
    assert abs(r["field_estimate"] - 1e-9) < 5e-12
    # sensitivity sits near the projection-noise limit (O(1) prefactor, here ~e)
    assert 1.5 < r["asd_over_limit"] < 4.0
    assert r["sensitivity_asd"] > 0.0


def test_more_atoms_improves_sensitivity():
    few = run_magnetometer(n_ticks=80, cycles_per_tick=3000, N_atoms=1e11, seed=1)
    many = run_magnetometer(n_ticks=80, cycles_per_tick=3000, N_atoms=1e13, seed=1)
    assert many["sensitivity_asd"] < few["sensitivity_asd"]


# --- typed-signal generality (non-QKD signal types) ----------------------
def test_ports_use_environmental_and_quantum_state_types():
    _g, _sched, _probe, backend, _prm = build_magnetometer()
    field = AmbientField("f", B_dc=0.0)
    cell = AtomicVaporCell("c", backend=backend, T1=1e-2, T2=5e-3, tau=5e-3)
    probe = ProbeReadout("p", backend=backend, N_atoms=1e12, tau=5e-3)
    assert field.ports_out["B"] is SignalType.ENVIRONMENTAL  # QKD never emitted this type
    assert cell.ports_out["spin"] is SignalType.QUANTUM_STATE
    assert probe.ports_in["spin"] is SignalType.QUANTUM_STATE


def test_graph_rejects_mismatched_port_types():
    """The kernel's build-time type check must reject wiring B-field into a spin port."""
    backend = SpinEnsembleBackend()
    field = AmbientField("f", B_dc=0.0)
    probe = ProbeReadout("p", backend=backend, N_atoms=1e12, tau=5e-3)
    g = DeviceGraph()
    g.add(field)
    g.add(probe)
    try:
        g.connect("f", "B", "p", "spin")  # ENVIRONMENTAL -> QUANTUM_STATE: illegal
    except TypeError:
        return
    raise AssertionError("expected a TypeError for mismatched port types")


# --- reuse of the domain-agnostic sweep harness --------------------------
def test_sweep_harness_reused_for_sensitivity_curve():
    def run_fn(**kw):
        return run_magnetometer(n_ticks=40, cycles_per_tick=2000, seed=2, **kw)

    res = sweep(run_fn, {"N_atoms": [1e11, 1e12, 1e13]})
    asd = res.metrics["sensitivity_asd"]
    # sensitivity floor falls monotonically as atom number rises
    assert asd[0] > asd[1] > asd[2]
