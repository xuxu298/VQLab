"""Declarative scenario files (spec §9) — shareable, reproducible experiments.

A scenario is a small YAML/dict naming a registered *runner* (`kind`) plus its parameters
and run settings; `run_scenario` dispatches to the runner and returns a metrics dict. This
makes an experiment a single shareable file — "here's exactly what I ran and measured."

The kernel only provides the registry mechanism; runners are registered by PLUGINS on
import (the kernel never imports a plugin). Import the plugin's `scenarios` module to make
its `kind`s available, then call `run_scenario`. `qsim.load_scenario_plugins()` does this
for the shipped QKD/QRNG plugins.
"""
from __future__ import annotations

from pathlib import Path

import yaml

SCENARIO_RUNNERS: dict[str, callable] = {}


def register_runner(kind: str):
    """Decorator: register a scenario runner under `kind`. Runner signature: spec -> dict."""
    def deco(fn):
        SCENARIO_RUNNERS[kind] = fn
        return fn
    return deco


def available_kinds() -> list[str]:
    return sorted(SCENARIO_RUNNERS)


def run_scenario(spec) -> dict:
    """Run a scenario given a dict or a path to a YAML file. Returns the metrics dict."""
    if isinstance(spec, (str, Path)):
        spec = yaml.safe_load(Path(spec).read_text())
    kind = spec.get("kind")
    if kind not in SCENARIO_RUNNERS:
        raise KeyError(
            f"unknown scenario kind {kind!r}; registered: {available_kinds()} "
            f"(did you import the plugin's scenarios module / call load_scenario_plugins()?)"
        )
    return SCENARIO_RUNNERS[kind](spec)
