"""QKD scenario runners — registered on import (the kernel never imports this)."""
from __future__ import annotations

import numpy as np

from ..core.scenario import register_runner
from .keyrate import skr_from_rates
from .reference import build_bb84_slice, build_decoy_bb84, load_default_profile


def _profile(spec):
    return load_default_profile()   # (future: load a named profile path from spec)


@register_runner("decoy_bb84")
def run_decoy_bb84(spec: dict) -> dict:
    """Full 1-decoy BB84 reference design -> engine-driven finite-key SKR."""
    prof = _profile(spec)
    run = spec.get("run", {})
    args = spec.get("builder_args", {})
    _g, sched, det, _amzi = build_decoy_bb84(prof, **args)
    sched.run(
        n_ticks=int(run.get("n_ticks", 300)),
        dt_slow=float(run.get("dt_slow", 1e-3)),
        pulses_per_tick=int(run.get("pulses_per_tick", 200_000)),
        rng=np.random.default_rng(int(run.get("seed", 0))),
    )
    rates = det.rates()
    fk = spec.get("finite_key", {})
    skr, kr = skr_from_rates(
        rates,
        mu1=prof.value("mu1"), mu2=prof.value("mu2"),
        p_mu1=prof.value("p_mu1"), p_Z=prof.value("p_Z"),
        n_Z_block=float(fk.get("n_Z_block", 1e9)),
        rep_rate=prof.value("rep_rate"),
        eps_sec=float(fk.get("eps_sec", 1e-9)),
        eps_cor=float(fk.get("eps_cor", 1e-15)),
        f_ec=float(fk.get("f_ec", 1.16)),
    )
    return {
        "skr_hz": skr,
        "key_length": kr.length,
        "l_over_nZ": kr.length / kr.nZ if kr.nZ else 0.0,
        "qber_Z": (rates["E_Z1"]),
        "qber_X": (rates["E_X1"]),
        "phiZ_u": kr.phiZ_u,
        "feasible": kr.feasible,
    }


@register_runner("bb84_slice")
def run_bb84_slice(spec: dict) -> dict:
    """M0 single-intensity slice -> running QBER / gain / (asymptotic) SKR."""
    prof = _profile(spec)
    run = spec.get("run", {})
    args = spec.get("builder_args", {})
    _g, sched, det, _amzi = build_bb84_slice(prof, **args)
    recs = sched.run(
        n_ticks=int(run.get("n_ticks", 50)),
        dt_slow=float(run.get("dt_slow", 1e-3)),
        pulses_per_tick=int(run.get("pulses_per_tick", 200_000)),
        rng=np.random.default_rng(int(run.get("seed", 0))),
    )
    last = recs[-1]
    return {"qber": last.get("qber", 0.0), "gain": last.get("gain", 0.0),
            "skr": last.get("skr", 0.0)}
