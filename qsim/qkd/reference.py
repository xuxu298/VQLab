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
from .blocks import (
    BobAMZI,
    DecoyBB84Detector,
    DecoyBB84Source,
    FaintPulseSource,
    FiberChannel,
    GatedInGaAsDetector,
)

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


def build_decoy_bb84(
    profile: CalibrationProfile | None = None,
    *,
    length_km: float = 25.0,
    locked: bool = True,
):
    """Full 1-decoy BB84 slice (M1): decoy source -> fiber -> AMZI -> sifting detector that
    accumulates the per-(basis, intensity) counts the Rusca finite-key bound consumes.
    Returns (graph, scheduler, detector, amzi)."""
    p = profile or load_default_profile()

    src = DecoyBB84Source(
        "alice_src",
        mu1=p.value("mu1"), mu2=p.value("mu2"),
        p_mu1=p.value("p_mu1"), p_Z=p.value("p_Z"), rep_rate=p.value("rep_rate"),
    )
    fiber = FiberChannel("fiber", length_km=length_km, alpha_db_km=p.value("fiber_alpha"))
    drift = PhaseDriftOU(theta=p.value("drift_theta"), sigma=p.value("drift_sigma"))
    amzi = BobAMZI(
        "bob_amzi", t_bob=p.value("bob_transmittance"), visibility=p.value("visibility"),
        drift=drift, locked=locked,
    )
    det = DecoyBB84Detector(
        "detector",
        backend=FockBackend(),
        eta_det=p.value("eta_det"),
        dark=DarkCount(p.value("p_dark")),
        after=Afterpulsing(p.value("afterpulse_amp")),
        deadtime=DeadTime(p.value("dead_time")),
        e_Z=p.value("e_Z"),
    )

    g = DeviceGraph()
    for b in (src, fiber, amzi, det):
        g.add(b)
    g.connect("alice_src", "out", "fiber", "in")
    g.connect("fiber", "out", "bob_amzi", "in")
    g.connect("bob_amzi", "out", "detector", "in")

    return g, MultiRateScheduler(g), det, amzi
