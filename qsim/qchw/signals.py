"""QubitState — the fast-layer payload for the QC-hardware device.

Plugin-local (not in qsim/core), like the sensing SpinBatch: the MultiRateScheduler passes
the payload opaquely, so a third, structurally different payload — an n-qubit density matrix
plus a shot count — flows through the unchanged kernel. Unlike a PulseBatch/SpinBatch (a
vector of independent stochastic events), one circuit produces ONE rho with exact outcome
probabilities; the shot count `n` is how many computational-basis samples the readout draws.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class QubitState:
    n_qubits: int
    rho: np.ndarray                 # 2^n x 2^n density matrix
    shots: int = 0                  # measurement samples to draw at readout this tick
    meta: dict = field(default_factory=dict)
