"""QC-hardware scenario runners — registered on import (spec §9).

Two kinds: `rb` runs randomized benchmarking and reports the error-per-Clifford against the
analytic channel infidelity; `bell_device` runs the multi-qubit Bell generator on the kernel.
"""
from __future__ import annotations

from ..core.scenario import register_runner
from .reference import run_bell_device
from .validation import validate_rb


@register_runner("rb")
def run_rb_scenario(spec: dict) -> dict:
    """Randomized benchmarking -> error-per-Clifford vs analytic channel infidelity."""
    a = spec.get("builder_args", {})
    run = spec.get("run", {})
    c = validate_rb(
        T1=float(a.get("T1", 50e-6)), T2=float(a.get("T2", 40e-6)),
        t_gate=float(a.get("t_gate", 30e-9)),
        n_seq=int(run.get("n_seq", 80)), seed=int(run.get("seed", 2)),
    )
    return {"epc": c.epc, "analytic_infidelity": c.analytic_infidelity,
            "ratio": c.ratio, "p": c.p}


@register_runner("bell_device")
def run_bell_scenario(spec: dict) -> dict:
    """Noisy 2-qubit Bell generator on the kernel -> fidelity + parity success."""
    a = spec.get("builder_args", {})
    run = spec.get("run", {})
    return run_bell_device(
        n_ticks=int(run.get("n_ticks", 200)),
        shots_per_tick=int(run.get("shots_per_tick", 256)),
        seed=int(run.get("seed", 0)),
        **a,
    )
