"""Build & run a beam-splitter QRNG on the kernel — the modularity proof.

Same kernel (graph + multi-rate scheduler + FockBackend + DarkCount) as the QKD plugin,
wired into a different device with a different metric set.
"""
from __future__ import annotations

import numpy as np

from ..core.backends import FockBackend
from ..core.graph import DeviceGraph
from ..core.impairments import DarkCount
from ..core.scheduler import MultiRateScheduler
from .blocks import BeamsplitterQRNG, QRNGSource
from .metrics import bias, min_entropy, sift_efficiency


def build_qrng(*, mu: float = 0.5, rep_rate: float = 1e8,
               eta_a: float = 0.20, eta_b: float = 0.20,
               p_dark_a: float = 1e-5, p_dark_b: float = 1e-5):
    src = QRNGSource("qrng_src", mu=mu, rep_rate=rep_rate)
    bs = BeamsplitterQRNG("bs_qrng", backend=FockBackend(), eta_a=eta_a, eta_b=eta_b,
                          dark_a=DarkCount(p_dark_a), dark_b=DarkCount(p_dark_b))
    g = DeviceGraph()
    g.add(src)
    g.add(bs)
    g.connect("qrng_src", "out", "bs_qrng", "in")
    return g, MultiRateScheduler(g), bs


def run_qrng(*, n_ticks: int = 200, pulses_per_tick: int = 200_000, seed: int = 0, **kw) -> dict:
    """Run the QRNG and return its randomness metrics."""
    _g, sched, bs = build_qrng(**kw)
    sched.run(n_ticks=n_ticks, dt_slow=1e-3, pulses_per_tick=pulses_per_tick,
              rng=np.random.default_rng(seed))
    n0, n1, nd = bs.counts()
    return {
        "n0": n0, "n1": n1, "n_discard": nd,
        "bias": bias(n0, n1),
        "min_entropy": min_entropy(n0, n1),
        "sift_efficiency": sift_efficiency(n0, n1, nd),
    }
