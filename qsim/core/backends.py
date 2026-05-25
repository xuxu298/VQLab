"""Pluggable quantum-state backends (spec §3) — the generalization lever.

M0 ships only FockBackend (photon-number statistics for faint pulses). Sensing will add
a Bloch-ensemble backend and QC-hardware a density-matrix/Lindblad backend (both via
QuTiP) WITHOUT touching the kernel — that is the whole point of this interface.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class QuantumStateBackend(Protocol):
    name: str

    def signal_click_prob(self, mu_eff: np.ndarray, eta: float) -> np.ndarray:
        """Probability a threshold detector clicks on the signal, per pulse."""
        ...


class FockBackend:
    """Faint-pulse / photon-number backend.

    A weak coherent pulse has Poissonian photon number with mean mu. After an overall
    transmittance/efficiency eta, the detected-photon count is Poisson(mu*eta), so a
    (non-photon-number-resolving) threshold detector clicks with probability
    1 - exp(-mu*eta). This is the standard faint-coherent-source detection model.
    """

    name = "fock"

    def signal_click_prob(self, mu_eff: np.ndarray, eta: float) -> np.ndarray:
        return 1.0 - np.exp(-mu_eff * eta)
