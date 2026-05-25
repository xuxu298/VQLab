"""qsim.qkd — the QKD domain plugin (first reference design).

Registers QKD blocks (faint-pulse source, fiber, Bob AMZI with phase drift, gated
InGaAs detector), QKD metrics (QBER, secret-key rate), and a builder for the M0
decoy-BB84 (signal-only in M0) vertical slice. The kernel (qsim.core) never imports this.
"""

from .blocks import FaintPulseSource, FiberChannel, BobAMZI, GatedInGaAsDetector
from .metrics import binary_entropy, secret_fraction
from .reference import build_bb84_slice

__all__ = [
    "FaintPulseSource",
    "FiberChannel",
    "BobAMZI",
    "GatedInGaAsDetector",
    "binary_entropy",
    "secret_fraction",
    "build_bb84_slice",
]
