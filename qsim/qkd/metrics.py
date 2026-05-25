"""QKD metrics (spec §9, QKD column).

NOTE (honesty / spec design-principle #4): secret_fraction here is the *simplified
asymptotic* BB84 lower bound. It is adequate to show the right QBER/SKR-vs-distance
shape for M0, but it is NOT the full decoy-state finite-key bound (Lim 2014 / Rusca
2018) — implementing and *validating that against a published experiment* is the M1
milestone. Do not quote M0 SKR numbers as production figures.
"""
from __future__ import annotations

import numpy as np


def binary_entropy(p: float | np.ndarray) -> float | np.ndarray:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -p * np.log2(p) - (1 - p) * np.log2(1 - p)


def secret_fraction(qber: float, f_ec: float = 1.16) -> float:
    """Secret bits per sifted detection (asymptotic BB84):
        r = 1 - h(e) [privacy amplification] - f_ec * h(e) [error correction],
    clamped to >= 0. Crosses zero near QBER ~ 11% (the classic BB84 threshold).
    """
    r = 1.0 - binary_entropy(qber) - f_ec * binary_entropy(qber)
    return float(max(0.0, r))
