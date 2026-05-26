"""QRNG scenario runner — registered on import."""
from __future__ import annotations

from ..core.scenario import register_runner
from .reference import run_qrng


@register_runner("qrng")
def run_qrng_scenario(spec: dict) -> dict:
    """Beam-splitter QRNG -> bias / min-entropy / sift-efficiency."""
    run = spec.get("run", {})
    args = spec.get("builder_args", {})
    return run_qrng(
        n_ticks=int(run.get("n_ticks", 200)),
        pulses_per_tick=int(run.get("pulses_per_tick", 200_000)),
        seed=int(run.get("seed", 0)),
        **args,
    )
