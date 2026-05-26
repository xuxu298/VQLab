"""QRNG randomness metrics (spec §9 — per-domain metrics).

For a raw bit stream the security-relevant quantity is the *min-entropy* per bit (it sets
how much extractable randomness a randomness extractor can output), not the Shannon entropy:
a biased source still has near-1 Shannon entropy but much less min-entropy.
"""
from __future__ import annotations

import math


def bias(n0: int, n1: int) -> float:
    """|P(1) - 1/2| of the kept single-click bits."""
    tot = n0 + n1
    return abs(n1 / tot - 0.5) if tot else 0.0


def p_max(n0: int, n1: int) -> float:
    tot = n0 + n1
    if not tot:
        return 1.0
    p1 = n1 / tot
    return max(p1, 1.0 - p1)


def min_entropy(n0: int, n1: int) -> float:
    """H_min = -log2(max(p0, p1)) bits per kept bit (extractable randomness per raw bit)."""
    return -math.log2(p_max(n0, n1))


def sift_efficiency(n0: int, n1: int, n_discard: int) -> float:
    """Fraction of pulses yielding a usable single-click bit (raw bit rate factor)."""
    tot = n0 + n1 + n_discard
    return (n0 + n1) / tot if tot else 0.0
