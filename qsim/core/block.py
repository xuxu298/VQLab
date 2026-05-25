"""Block base class + the two-layer execution protocol (spec §4, §6).

Every device component is a Block with typed ports. It may participate in:
  - the SLOW layer  -> step(ctx):  drift, control loops, quasi-static parameter updates
  - the FAST layer  -> process(batch, ctx): transforms a PulseBatch (event-rate physics)
A block can implement either or both.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .signals import PulseBatch, SignalType


class Timescale(Enum):
    """Declared natural rate of a block/impairment so the scheduler drives it correctly."""

    STATIC = "static"          # constant (insertion loss, efficiency)
    PER_EVENT = "per_event"    # resampled every pulse (jitter, shot noise, dark counts)
    STATEFUL = "stateful"      # depends on recent history (afterpulsing, dead time)
    SLOW_DRIFT = "slow_drift"  # ms->hours (bias/phase drift, temperature)


@dataclass
class SimContext:
    """Shared per-step context handed to every block (spec §6)."""

    t: float                      # current sim time (s)
    dt: float                     # slow-layer step (s)
    rng: np.random.Generator
    shared: dict = field(default_factory=dict)  # cross-block scratch (e.g. current e_opt)


class Block:
    """Base class for all device blocks."""

    def __init__(self, name: str, timescale: Timescale = Timescale.STATIC):
        self.name = name
        self.timescale = timescale
        self.ports_in: dict[str, "SignalType"] = {}
        self.ports_out: dict[str, "SignalType"] = {}

    # --- slow layer -------------------------------------------------------
    def step(self, ctx: SimContext) -> None:
        """Advance slow internal state (drift, control). Default: no-op."""

    # --- fast layer -------------------------------------------------------
    def process(self, batch: "PulseBatch | None", ctx: SimContext) -> "PulseBatch":
        """Transform/produce a PulseBatch. Default: pass through unchanged."""
        return batch

    def reset(self) -> None:
        """Reset accumulators/state (used between parameter sweeps)."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} {self.name!r}>"
