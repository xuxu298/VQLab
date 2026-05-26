"""Typed signals that flow on the edges of a DeviceGraph.

Spec ref: docs/02 §2 (signal types) and §6 (the fast layer carries *batches* of pulses
so we can simulate billions of pulses statistically instead of one ps-event at a time).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np


class SignalType(Enum):
    """The port/edge types the kernel type-checks at graph-build time (spec §2)."""

    OPTICAL = auto()        # carries a quantum/classical optical mode (here: a PulseBatch)
    ELECTRICAL = auto()     # analog voltage/current waveform (SPICE co-sim, drivers)
    QUANTUM_STATE = auto()  # abstract quantum-state carrier (backend-dependent)
    CONTROL = auto()        # digital/logical: triggers, clock, DAC setpoints
    ENVIRONMENTAL = auto()  # scalar/vector fields: temperature, B-field, vibration
    CLASSICAL = auto()      # bits / messages / frames (post-processing, networking)


@dataclass
class PulseBatch:
    """A vectorised batch of optical pulses — the payload on OPTICAL edges in M0.

    Rather than emit one pulse-event every clock period (intractable for 1e9 pulses
    over hours), the fast layer pushes a statistically-representative *batch* through
    the block chain; metrics accumulate across batches while the slow layer (drift,
    control) evolves between them. This is the multi-rate aggregation of spec §6.
    """

    n: int
    bit: np.ndarray          # Alice's bit per pulse (0/1)
    basis_a: np.ndarray      # Alice's basis per pulse (0=Z key / 1=X test)
    basis_b: np.ndarray      # Bob's measurement basis per pulse (0=Z / 1=X)
    intensity: np.ndarray    # source mean photon number mu per pulse (signal vs decoy)
    mu_eff: np.ndarray       # running mean photons reaching the detector (channels multiply)
    intensity_idx: np.ndarray | None = None  # 1=signal mu1, 2=decoy mu2 (decoy protocol)

    # Filled in by the detector block:
    clicked: np.ndarray | None = None   # did a detection event occur?
    error: np.ndarray | None = None     # was the sifted bit wrong?
    sifted: np.ndarray | None = None    # did Alice/Bob bases match (kept after sifting)?

    meta: dict = field(default_factory=dict)
