"""SpinBatch — the fast-layer payload for the sensing device.

Deliberately defined in the *plugin*, not in qsim/core/signals.py: the MultiRateScheduler
passes the batch object opaquely (`batch = b.process(batch, ctx)`) and never inspects it, so
a domain can ship its own payload with zero kernel edits. That a totally different payload
than QKD's PulseBatch flows through the unchanged scheduler is part of the M3 generality
proof. Like PulseBatch, a SpinBatch is a *vectorised batch* of independent measurement
cycles (not one cycle at a time), so billions of cycles aggregate statistically (spec §6).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class SpinBatch:
    n: int                          # number of independent measurement cycles in the batch
    B_true: np.ndarray              # the field each cycle actually sees (T) — set by AmbientField
    sx: np.ndarray | None = None    # transverse spin x-quadrature after interrogation (cell)
    sy: np.ndarray | None = None    # transverse spin y-quadrature after interrogation (cell)
    B_est: np.ndarray | None = None  # per-cycle field estimate (T) — set by ProbeReadout
    meta: dict = field(default_factory=dict)
