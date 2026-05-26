"""Build & run the QC-hardware reference device on the kernel — the M4 modularity proof.

Same kernel as QKD/QRNG/sensing (DeviceGraph + MultiRateScheduler + CalibrationProfile +
PhaseDriftOU), wired into a noisy multi-qubit processor with its own density-matrix backend,
payload and metrics. No kernel code is added or changed.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..core.calibration import CalibrationProfile
from ..core.graph import DeviceGraph
from ..core.scheduler import MultiRateScheduler
from .backend import DensityMatrixBackend, cnot, embed, H, rz
from .blocks import BELL, BellCircuit, BellReadout, QubitRegister

DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "profiles" / "transmon_2q.yaml"


def load_default_profile() -> CalibrationProfile:
    return CalibrationProfile.from_yaml(DEFAULT_PROFILE)


def bell_fidelity_under_noise(*, T1: float, T2: float, t_gate: float,
                              eps: float = 0.0) -> float:
    """Prepare a Bell pair (H, CNOT) with T1/T2 relaxation per gate + optional coherent
    over-rotation eps, and return the state fidelity to (|00>+|11>)/sqrt(2).

    A direct two-qubit entanglement check (the capability M3's single spin could not show):
    eps=0 and t_gate->0 gives unit fidelity; relaxation and miscalibration degrade it."""
    be = DensityMatrixBackend(2, T1=T1, T2=T2)
    noise = be.relax_channel_matrix(t_gate)
    rho = be.zero_state()
    rho = be.apply_channel(be.apply_unitary(rho, embed(H, 0, 2)), noise)
    if eps:
        rho = be.apply_unitary(rho, embed(rz(eps), 0, 2))
    rho = be.apply_channel(be.apply_unitary(rho, cnot(0, 1, 2)), noise)
    return be.fidelity_pure(rho, BELL)


def build_bell_device(profile: CalibrationProfile | None = None, *,
                      T1: float | None = None, T2: float | None = None,
                      t_gate: float | None = None, miscal_sigma: float | None = None):
    """Wire QubitRegister -> BellCircuit -> BellReadout into a graph + scheduler."""
    p = profile or load_default_profile()
    T1 = p.value("T1") if T1 is None else T1
    T2 = p.value("T2") if T2 is None else T2
    t_gate = p.value("t_gate") if t_gate is None else t_gate
    miscal_sigma = p.value("miscal_sigma") if miscal_sigma is None else miscal_sigma

    backend = DensityMatrixBackend(2, T1=T1, T2=T2)
    reg = QubitRegister("reg", backend=backend)
    circ = BellCircuit("bell", backend=backend, t_gate=t_gate,
                       miscal_sigma=miscal_sigma, miscal_theta=p.value("miscal_theta"))
    rdo = BellReadout("readout", backend=backend)

    g = DeviceGraph()
    for b in (reg, circ, rdo):
        g.add(b)
    g.connect("reg", "q", "bell", "q")
    g.connect("bell", "q", "readout", "q")
    return g, MultiRateScheduler(g), rdo, {"T1": T1, "T2": T2, "t_gate": t_gate}


def run_bell_device(*, n_ticks: int = 200, shots_per_tick: int = 256, seed: int = 0,
                    profile: CalibrationProfile | None = None, **build_kw) -> dict:
    """Run the Bell device on the kernel and return fidelity metrics."""
    _g, sched, rdo, prm = build_bell_device(profile=profile, **build_kw)
    sched.run(n_ticks=n_ticks, dt_slow=1e-6, pulses_per_tick=shots_per_tick,
              rng=np.random.default_rng(seed))
    mean_fid, parity = rdo.stats()
    return {
        "mean_bell_fidelity": mean_fid,
        "parity_success": parity,          # shot-estimated P(00)+P(11)
        "T1": prm["T1"], "T2": prm["T2"], "t_gate": prm["t_gate"],
    }
