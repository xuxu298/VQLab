"""qsim.qrng — quantum RNG plugin.

A beam-splitter QRNG built entirely from kernel primitives (no new kernel code), proving the
domain-agnostic kernel hosts a second quantum-technology domain cheaply (spec §10, M2).
"""
from .blocks import BeamsplitterQRNG, QRNGSource
from .metrics import bias, min_entropy, p_max, sift_efficiency
from .reference import build_qrng, run_qrng

__all__ = [
    "QRNGSource",
    "BeamsplitterQRNG",
    "build_qrng",
    "run_qrng",
    "bias",
    "min_entropy",
    "p_max",
    "sift_efficiency",
]
