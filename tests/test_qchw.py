"""Tests for the qchw plugin (M4) — multi-qubit QC-hardware on the kernel.

Covers the two-tier validation evidence (Lindblad vs closed form; RB error-per-Clifford vs
the analytic channel infidelity), the genuinely-new multi-qubit/entanglement capability, the
device running on the unchanged kernel, typed-port checks, and reuse of the sweep harness.
"""
import numpy as np

from qsim.core.graph import DeviceGraph
from qsim.core.signals import SignalType
from qsim.core.sweep import sweep
from qsim.qchw.backend import DensityMatrixBackend, X
from qsim.qchw.blocks import BellReadout, QubitRegister
from qsim.qchw.cliffords import CliffordGroup
from qsim.qchw.metrics import error_per_clifford
from qsim.qchw.reference import bell_fidelity_under_noise, run_bell_device
from qsim.qchw.validation import validate_lindblad, validate_rb


# --- Tier 1: backend correctness -----------------------------------------
def test_lindblad_matches_closed_form():
    c = validate_lindblad()
    assert c.max_abs_err < 1e-9          # expm is exact -> machine precision


def test_depolarizing_infidelity_exact():
    be = DensityMatrixBackend(1)
    p = 0.1
    vecI = np.eye(2).reshape(-1, order="F")
    chan = (1 - p) * np.eye(4) + p * np.outer(vecI * 0.5, vecI.conj())
    assert abs(be.avg_gate_infidelity(chan) - p / 2) < 1e-9
    assert be.avg_gate_infidelity(np.eye(4)) < 1e-12   # identity channel: zero infidelity


# --- Tier 2: RB recovers the gate error ----------------------------------
def test_rb_recovers_analytic_infidelity():
    c = validate_rb(T1=50e-6, T2=40e-6, t_gate=30e-9, n_seq=50, seed=2)
    assert 0.85 < c.ratio < 1.18          # RB EPC matches the analytic channel infidelity
    assert c.epc > 0.0


def test_error_per_clifford_formula():
    assert error_per_clifford(1.0) == 0.0
    assert abs(error_per_clifford(0.99) - 0.005) < 1e-12   # (1-p)(d-1)/d, d=2


# --- Clifford group ------------------------------------------------------
def test_clifford_group_is_24_and_closed():
    g = CliffordGroup()
    assert len(g) == 24
    rng = np.random.default_rng(0)
    for _ in range(300):
        i, j = rng.integers(0, 24, 2)
        g.inverse_of_product(g.elements[i] @ g.elements[j])   # raises if not closed


# --- multi-qubit / entanglement (new vs M3) ------------------------------
def test_bell_fidelity_ideal_and_degraded():
    assert abs(bell_fidelity_under_noise(T1=np.inf, T2=np.inf, t_gate=0.0) - 1.0) < 1e-12
    # a pure RZ over-rotation eps gives fidelity cos^2(eps/2)
    f = bell_fidelity_under_noise(T1=np.inf, T2=np.inf, t_gate=0.0, eps=1.0)
    assert abs(f - np.cos(0.5) ** 2) < 1e-9
    # relaxation strictly degrades the prepared state
    assert bell_fidelity_under_noise(T1=50e-6, T2=70e-6, t_gate=40e-9) < 1.0


def test_longer_gates_lower_bell_fidelity():
    fast = bell_fidelity_under_noise(T1=50e-6, T2=70e-6, t_gate=20e-9)
    slow = bell_fidelity_under_noise(T1=50e-6, T2=70e-6, t_gate=200e-9)
    assert slow < fast


# --- the device on the kernel --------------------------------------------
def test_bell_device_runs_on_kernel():
    r = run_bell_device(n_ticks=80, shots_per_tick=256, seed=0)
    assert 0.99 < r["mean_bell_fidelity"] <= 1.0
    assert 0.0 <= r["parity_success"] <= 1.0


def test_slow_drift_degrades_fidelity_but_not_parity():
    base = run_bell_device(n_ticks=120, shots_per_tick=512, seed=0)
    drift = run_bell_device(n_ticks=120, shots_per_tick=512, seed=0, miscal_sigma=120.0)
    # coherent phase drift lowers the mean fidelity ...
    assert drift["mean_bell_fidelity"] < base["mean_bell_fidelity"] - 0.02
    # ... but computational-basis parity is blind to a phase error (the teaching point)
    assert abs(drift["parity_success"] - base["parity_success"]) < 0.01


# --- typed-signal generality ---------------------------------------------
def test_quantum_state_ports_and_type_checking():
    be = DensityMatrixBackend(2)
    reg = QubitRegister("reg", backend=be)
    rdo = BellReadout("rdo", backend=be)
    assert reg.ports_out["q"] is SignalType.QUANTUM_STATE
    assert rdo.ports_in["q"] is SignalType.QUANTUM_STATE
    g = DeviceGraph()
    g.add(reg)
    g.add(rdo)
    g.connect("reg", "q", "rdo", "q")     # QUANTUM_STATE -> QUANTUM_STATE: legal


# --- sweep-harness reuse -------------------------------------------------
def test_sweep_harness_reused_for_gate_time():
    def run_fn(**kw):
        return run_bell_device(n_ticks=40, shots_per_tick=128, seed=1, **kw)

    res = sweep(run_fn, {"t_gate": [20e-9, 80e-9, 200e-9]})
    fid = res.metrics["mean_bell_fidelity"]
    assert fid[0] > fid[1] > fid[2]       # longer gates -> more relaxation -> lower fidelity
