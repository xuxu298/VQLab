"""QRNG plugin blocks — a beam-splitter quantum RNG built from the SAME kernel pieces as
the QKD plugin (spec §10: "qrng — trivial early plugin (reuses qkd source+detector) —
proves modularity cheaply").

Device: a faint pulse hits a 50/50 beam splitter and is detected by two single-photon
detectors A/B; the raw bit is *which* detector clicked. The randomness is only as good as
the device: detector efficiency mismatch and asymmetric dark counts bias the bit, lowering
the extractable (min-)entropy. This reuses the kernel Block/scheduler, the FockBackend, and
the DarkCount/Afterpulsing impairments — no new kernel code, which is the whole point.
"""
from __future__ import annotations

import numpy as np

from ..core.backends import FockBackend, QuantumStateBackend
from ..core.block import Block, SimContext, Timescale
from ..core.impairments import DarkCount
from ..core.signals import PulseBatch, SignalType


class QRNGSource(Block):
    """Faint pulses for the QRNG (no bit/basis encoding — randomness comes from detection)."""

    def __init__(self, name: str, mu: float, rep_rate: float):
        super().__init__(name, Timescale.STATIC)
        self.mu = float(mu)
        self.rep_rate = float(rep_rate)
        self.ports_out = {"out": SignalType.OPTICAL}

    def process(self, batch: PulseBatch | None, ctx: SimContext) -> PulseBatch:
        n = int(ctx.shared["pulses"])
        ctx.shared["rep_rate"] = self.rep_rate
        mu = np.full(n, self.mu)
        z = np.zeros(n, dtype=int)
        return PulseBatch(n=n, bit=z, basis_a=z, basis_b=z, intensity=mu, mu_eff=mu.copy())


class BeamsplitterQRNG(Block):
    """50/50 splitter + two threshold detectors A/B. Raw bit = which detector clicked.

    Only single-click events are kept (no click / double click discarded). Accumulates the
    0/1 counts so the randomness metrics (bias, min-entropy) can be read out. Detector
    efficiency mismatch (eta_a vs eta_b) and dark-count asymmetry are the bias sources the
    batched model captures faithfully; afterpulse-induced *serial* correlations need the
    per-event model (same limitation surfaced in M0's validation) and are out of scope here.
    """

    def __init__(self, name: str, backend: QuantumStateBackend, eta_a: float, eta_b: float,
                 dark_a: DarkCount, dark_b: DarkCount):
        super().__init__(name, Timescale.PER_EVENT)
        self.backend = backend
        self.eta_a, self.eta_b = float(eta_a), float(eta_b)
        self.dark_a, self.dark_b = dark_a, dark_b
        self.ports_in = {"in": SignalType.OPTICAL}
        self.reset()

    def reset(self) -> None:
        self.n0 = 0      # single clicks in A  (bit 0)
        self.n1 = 0      # single clicks in B  (bit 1)
        self.n_discard = 0

    def process(self, batch: PulseBatch, ctx: SimContext) -> PulseBatch:
        rng = ctx.rng
        n = batch.n
        half = 0.5 * batch.mu_eff                       # 50/50 split
        pa = 1.0 - (1.0 - self.backend.signal_click_prob(half, self.eta_a)) * (1.0 - self.dark_a.p_dc)
        pb = 1.0 - (1.0 - self.backend.signal_click_prob(half, self.eta_b)) * (1.0 - self.dark_b.p_dc)
        click_a = rng.random(n) < pa
        click_b = rng.random(n) < pb
        single = click_a ^ click_b
        bit1 = single & click_b
        self.n0 += int(np.count_nonzero(single & click_a))
        self.n1 += int(np.count_nonzero(bit1))
        self.n_discard += int(np.count_nonzero(~single))

        batch.clicked = click_a | click_b
        batch.bit = bit1.astype(int)
        batch.sifted = single
        return batch

    def counts(self) -> tuple[int, int, int]:
        return self.n0, self.n1, self.n_discard
