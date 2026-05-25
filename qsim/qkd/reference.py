"""Builder for the M0 BB84 vertical slice (the first reference design).

build_bb84_slice() wires Alice source -> fiber -> Bob AMZI -> detector into a
DeviceGraph and returns it with a ready MultiRateScheduler and handles to the detector
and AMZI (for sweeps / toggling the phase lock).
"""
from __future__ import annotations

from pathlib import Path

from ..core.backends import FockBackend
from ..core.calibration import CalibrationProfile
from ..core.graph import DeviceGraph
from ..core.impairments import Afterpulsing, DarkCount, DeadTime, PhaseDriftOU
from ..core.scheduler import MultiRateScheduler
from .blocks import BobAMZI, FaintPulseSource, FiberChannel, GatedInGaAsDetector

DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "profiles" / "ingaas_spad.yaml"


def load_default_profile() -> CalibrationProfile:
    return CalibrationProfile.from_yaml(DEFAULT_PROFILE)


def build_bb84_slice(
    profile: CalibrationProfile | None = None,
    *,
    length_km: float = 25.0,
    locked: bool = True,
):
    p = profile or load_default_profile()

    src = FaintPulseSource("alice_src", mu_signal=p.value("mu_signal"), rep_rate=p.value("rep_rate"))
    fiber = FiberChannel("fiber", length_km=length_km, alpha_db_km=p.value("fiber_alpha"))
    drift = PhaseDriftOU(theta=p.value("drift_theta"), sigma=p.value("drift_sigma"))
    amzi = BobAMZI(
        "bob_amzi",
        t_bob=p.value("bob_transmittance"),
        visibility=p.value("visibility"),
        drift=drift,
        locked=locked,
    )
    det = GatedInGaAsDetector(
        "detector",
        backend=FockBackend(),
        eta_det=p.value("eta_det"),
        dark=DarkCount(p.value("p_dark")),
        after=Afterpulsing(p.value("afterpulse_amp")),
        deadtime=DeadTime(p.value("dead_time")),
    )

    g = DeviceGraph()
    for b in (src, fiber, amzi, det):
        g.add(b)
    g.connect("alice_src", "out", "fiber", "in")
    g.connect("fiber", "out", "bob_amzi", "in")
    g.connect("bob_amzi", "out", "detector", "in")

    return g, MultiRateScheduler(g), det, amzi
