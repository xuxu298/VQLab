"""Sensing-device blocks — an optically-pumped atomic magnetometer on the kernel.

Three blocks wired AmbientField -> AtomicVaporCell -> ProbeReadout exercise signal types
and a backend that QKD/QRNG never touched, while reusing the kernel's Block base, the
MultiRateScheduler, the PhaseDriftOU slow-drift impairment and the calibration profile:

  AmbientField   (out: ENVIRONMENTAL)  -- the B-field being sensed; a DC value plus slow
                                          OU drift. This is the first block in the whole
                                          project to emit on the ENVIRONMENTAL port.
  AtomicVaporCell (in: ENVIRONMENTAL,
                   out: QUANTUM_STATE)  -- precesses + relaxes the spin in the current field
                                          for the interrogation time via SpinEnsembleBackend.
  ProbeReadout   (in: QUANTUM_STATE)    -- measures the transverse spin with quantum
                                          projection noise, estimates the field, accumulates
                                          the statistics the sensitivity metric consumes.

Multi-rate structure mirrors the QKD slice exactly: AmbientField.step() walks the slow field
each tick; each tick then pushes one fast SpinBatch of many cycles through the chain, and the
estimate statistics accumulate across batches.
"""
from __future__ import annotations

import numpy as np

from ..core.block import Block, SimContext, Timescale
from ..core.impairments import PhaseDriftOU
from ..core.signals import SignalType
from .backend import SpinEnsembleBackend
from .signals import SpinBatch


class AmbientField(Block):
    """The magnetic field under test: a DC value plus slow Ornstein-Uhlenbeck drift (T).

    Reuses the kernel's PhaseDriftOU as a generic OU generator (the impairment is named for
    its first use in QKD, but the process is domain-agnostic) — the slow layer the
    magnetometer must track and reject, just as the AMZI phase was in QKD.
    """

    def __init__(self, name: str, B_dc: float, drift_sigma: float = 0.0,
                 drift_theta: float = 50.0):
        super().__init__(name, Timescale.SLOW_DRIFT)
        self.B_dc = float(B_dc)
        self.drift = PhaseDriftOU(theta=drift_theta, sigma=drift_sigma)
        self.B = self.B_dc
        self.ports_out = {"B": SignalType.ENVIRONMENTAL}

    def step(self, ctx: SimContext) -> None:
        self.B = self.B_dc + self.drift.step(ctx.dt, ctx.rng)
        ctx.shared["B_field"] = self.B

    def process(self, batch, ctx: SimContext) -> SpinBatch:
        n = int(ctx.shared["pulses"])  # "pulses" == cycles per tick (shared scheduler key)
        return SpinBatch(n=n, B_true=np.full(n, self.B))

    def reset(self) -> None:
        self.drift.reset()
        self.B = self.B_dc


class AtomicVaporCell(Block):
    """Optically-pumped spin ensemble. Prepares a transverse spin, precesses + relaxes it in
    the incoming field for the interrogation time `tau` via the Bloch backend, and outputs
    the (clean, noiseless) transverse quadratures. Readout noise belongs to the probe."""

    def __init__(self, name: str, backend: SpinEnsembleBackend, *, T1: float, T2: float,
                 tau: float, S0_pump: float = 1.0):
        super().__init__(name, Timescale.PER_EVENT)
        self.backend = backend
        self.T1, self.T2, self.tau = float(T1), float(T2), float(tau)
        self.S0_pump = float(S0_pump)
        self.ports_in = {"B": SignalType.ENVIRONMENTAL}
        self.ports_out = {"spin": SignalType.QUANTUM_STATE}

    def process(self, batch: SpinBatch, ctx: SimContext) -> SpinBatch:
        # The field is (quasi-)static over one interrogation, so use the exact closed form
        # rather than re-running RK4 per cycle — same physics, far cheaper for a batch.
        r = np.exp(-self.tau / self.T2)
        phi = self.backend.gamma * batch.B_true * self.tau   # Larmor phase per cycle
        batch.sx = r * np.cos(phi) * self.S0_pump
        batch.sy = -r * np.sin(phi) * self.S0_pump
        return batch


class ProbeReadout(Block):
    """Probe-laser readout + field estimator. Reads both transverse quadratures with quantum
    projection noise (std 1/sqrt(N) for N atoms) plus optional technical/probe noise, recovers
    the Larmor phase, and inverts to a field estimate. Accumulates running sum/sum-of-squares
    so the sensitivity metric can be read out without storing every cycle."""

    def __init__(self, name: str, backend: SpinEnsembleBackend, *, N_atoms: float,
                 tau: float, technical_noise: float = 0.0):
        super().__init__(name, Timescale.PER_EVENT)
        self.backend = backend
        self.N_atoms = float(N_atoms)
        self.tau = float(tau)
        self.technical_noise = float(technical_noise)  # extra readout std on each quadrature
        self.ports_in = {"spin": SignalType.QUANTUM_STATE}
        self.reset()

    def reset(self) -> None:
        self.n_cycles = 0
        self.sum_est = 0.0
        self.sumsq_est = 0.0

    def process(self, batch: SpinBatch, ctx: SimContext) -> SpinBatch:
        rng = ctx.rng
        n = batch.n
        sigma = np.hypot(self.backend.projection_noise_std(self.N_atoms), self.technical_noise)
        sx = batch.sx + rng.normal(0.0, sigma, n)
        sy = batch.sy + rng.normal(0.0, sigma, n)
        phi_hat = np.arctan2(-sy, sx)
        B_est = phi_hat / (self.backend.gamma * self.tau)
        batch.B_est = B_est

        self.n_cycles += n
        self.sum_est += float(np.sum(B_est))
        self.sumsq_est += float(np.sum(B_est * B_est))
        # expose the live field estimate for per-tick recording / a GUI strip-chart
        ctx.shared["metrics"] = {"B_est_tick": float(np.mean(B_est))}
        return batch

    def stats(self) -> tuple[int, float, float]:
        """(n_cycles, mean estimate, per-cycle std of the estimate)."""
        if self.n_cycles == 0:
            return 0, 0.0, 0.0
        mean = self.sum_est / self.n_cycles
        var = max(self.sumsq_est / self.n_cycles - mean * mean, 0.0)
        return self.n_cycles, mean, float(np.sqrt(var))
