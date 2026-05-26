"""Build & run the atomic magnetometer on the kernel — the M3 modularity proof.

Same kernel as QKD/QRNG (DeviceGraph + MultiRateScheduler + CalibrationProfile + the
PhaseDriftOU slow-drift impairment), wired into a physically unrelated device with its own
backend, payload and metrics. No kernel code is added or changed.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..core.calibration import CalibrationProfile
from ..core.graph import DeviceGraph
from ..core.scheduler import MultiRateScheduler
from .backend import SpinEnsembleBackend
from .blocks import AmbientField, AtomicVaporCell, ProbeReadout
from .metrics import projection_limit_asd, sensitivity_asd, sensitivity_over_time

DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "profiles" / "rb_magnetometer.yaml"


def load_default_profile() -> CalibrationProfile:
    return CalibrationProfile.from_yaml(DEFAULT_PROFILE)


def build_magnetometer(profile: CalibrationProfile | None = None, *,
                       B_dc: float | None = None, drift_sigma: float | None = None,
                       N_atoms: float | None = None, tau: float | None = None):
    """Wire AmbientField -> AtomicVaporCell -> ProbeReadout into a graph + scheduler.

    `N_atoms` and `tau` are exposed as overrides so the sweep/optimize harness can tune them
    (sensitivity vs atom number / interrogation time are the canonical magnetometer knobs).
    Returns (graph, scheduler, probe_readout, backend, params) — the readout carries the
    accumulated statistics the metrics consume.
    """
    p = profile or load_default_profile()
    gamma = p.value("gamma")
    T1, T2 = p.value("T1"), p.value("T2")
    tau = p.value("tau") if tau is None else float(tau)
    N = p.value("N_atoms") if N_atoms is None else float(N_atoms)
    backend = SpinEnsembleBackend(gamma=gamma)

    field = AmbientField(
        "ambient",
        B_dc=p.value("B_dc") if B_dc is None else B_dc,
        drift_sigma=p.value("drift_sigma") if drift_sigma is None else drift_sigma,
        drift_theta=p.value("drift_theta"),
    )
    cell = AtomicVaporCell("cell", backend=backend, T1=T1, T2=T2, tau=tau,
                           S0_pump=p.value("S0_pump"))
    probe = ProbeReadout("probe", backend=backend, N_atoms=N, tau=tau,
                         technical_noise=p.value("technical_noise"))

    g = DeviceGraph()
    for b in (field, cell, probe):
        g.add(b)
    g.connect("ambient", "B", "cell", "B")
    g.connect("cell", "spin", "probe", "spin")

    params = {"gamma": gamma, "T1": T1, "T2": T2, "tau": tau, "N_atoms": N}
    return g, MultiRateScheduler(g), probe, backend, params


def run_magnetometer(*, n_ticks: int = 200, cycles_per_tick: int = 2000, seed: int = 0,
                     profile: CalibrationProfile | None = None, **build_kw) -> dict:
    """Run the magnetometer and return its sensitivity metrics + recovered field.

    The slow clock advances by one interrogation time `tau` per tick; each tick reads
    `cycles_per_tick` independent measurement cycles. Total integration time = n_ticks *
    cycles_per_tick * tau.
    """
    _g, sched, probe, _backend, prm = build_magnetometer(profile=profile, **build_kw)
    tau = prm["tau"]
    sched.run(n_ticks=n_ticks, dt_slow=tau, pulses_per_tick=cycles_per_tick,
              rng=np.random.default_rng(seed))
    n_cycles, mean_est, sigma_cycle = probe.stats()
    t_total = n_cycles * tau
    asd = sensitivity_asd(sigma_cycle, tau)
    asd_limit = projection_limit_asd(N=prm["N_atoms"], T2=prm["T2"], gamma=prm["gamma"])
    return {
        "n_cycles": n_cycles,
        "t_total": t_total,
        "field_estimate": mean_est,
        "sigma_cycle": sigma_cycle,
        "sensitivity_asd": asd,                       # T/sqrt(Hz)
        "sensitivity_at_t": sensitivity_over_time(sigma_cycle, tau, t_total),  # T
        "projection_limit_asd": asd_limit,            # T/sqrt(Hz)
        "asd_over_limit": asd / asd_limit if asd_limit else float("nan"),
    }
