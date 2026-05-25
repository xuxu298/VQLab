"""Composable impairment models (spec §5).

Each impairment declares a Timescale so the scheduler/blocks know when to (re)evaluate
it. These are *behavioral* models calibrated to published values, not first-principles
device physics (spec design principle #3). Provenance for default values lives in
qsim/profiles/*.yaml.
"""
from __future__ import annotations

import numpy as np

from .block import Timescale


class Impairment:
    timescale: Timescale = Timescale.STATIC

    def reset(self) -> None:
        pass


class FixedEfficiency(Impairment):
    """Static multiplicative transmittance/efficiency (insertion loss, quantum eff.)."""

    timescale = Timescale.STATIC

    def __init__(self, eta: float):
        self.eta = float(eta)


class DarkCount(Impairment):
    """Per-gate dark-count click probability (thermal/tunnelling false counts)."""

    timescale = Timescale.PER_EVENT

    def __init__(self, p_dc: float):
        self.p_dc = float(p_dc)


class Afterpulsing(Impairment):
    """Afterpulsing: trapped carriers from a *previous* avalanche trigger a later false
    click — a non-Markovian, history-dependent effect. We use a mean-field behavioral
    model: the afterpulse probability on a gate is proportional to the recent click
    rate (an EMA), capturing the characteristic positive feedback (more clicks ->
    more afterpulses -> more clicks) without a full per-carrier Markov chain.

    Ref for the non-Markovian nature & typical magnitudes: gated InGaAs/InP SPAD
    characterisation, e.g. arXiv:1105.3760 (P_ap a few % at hundreds of MHz gating).
    """

    timescale = Timescale.STATEFUL

    def __init__(self, amplitude: float, memory: float = 0.2):
        self.amplitude = float(amplitude)   # afterpulse prob per unit recent click rate
        self.memory = float(memory)         # EMA weight for the new sample
        self._recent_rate = 0.0

    def p_afterpulse(self) -> float:
        return self.amplitude * self._recent_rate

    def update(self, click_rate: float) -> None:
        self._recent_rate = (1 - self.memory) * self._recent_rate + self.memory * click_rate

    def reset(self) -> None:
        self._recent_rate = 0.0


class DeadTime(Impairment):
    """Dead time after a click. At click rate R it reduces the live duty cycle by
    1/(1 + R*tau_dead) — negligible at metro count rates, but real at high rates."""

    timescale = Timescale.STATEFUL

    def __init__(self, tau_dead: float):
        self.tau_dead = float(tau_dead)

    def duty_factor(self, count_rate_hz: float) -> float:
        return 1.0 / (1.0 + count_rate_hz * self.tau_dead)


class PhaseDriftOU(Impairment):
    """Slow phase drift of an interferometer modelled as an Ornstein-Uhlenbeck process:
        dphi = -theta*phi*dt + sigma*sqrt(dt)*N(0,1)
    Stationary std = sigma/sqrt(2*theta). Represents thermal/mechanical drift away from
    the locked quadrature point (spec §5, slow-drift class)."""

    timescale = Timescale.SLOW_DRIFT

    def __init__(self, theta: float, sigma: float, phi0: float = 0.0):
        self.theta = float(theta)
        self.sigma = float(sigma)
        self.phi = float(phi0)

    def step(self, dt: float, rng: np.random.Generator) -> float:
        self.phi += -self.theta * self.phi * dt + self.sigma * np.sqrt(dt) * rng.standard_normal()
        return self.phi

    def reset(self) -> None:
        self.phi = 0.0
