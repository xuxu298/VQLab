"""Sensing scenario runner — registered on import (spec §9)."""
from __future__ import annotations

from ..core.scenario import register_runner
from .reference import run_magnetometer


@register_runner("magnetometer")
def run_magnetometer_scenario(spec: dict) -> dict:
    """Optically-pumped atomic magnetometer -> sensitivity (ASD) + recovered field."""
    run = spec.get("run", {})
    args = spec.get("builder_args", {})
    return run_magnetometer(
        n_ticks=int(run.get("n_ticks", 200)),
        cycles_per_tick=int(run.get("cycles_per_tick", 2000)),
        seed=int(run.get("seed", 0)),
        **args,
    )
