"""QKD device blocks for the M0 vertical slice.

Pipeline:  FaintPulseSource -> FiberChannel -> BobAMZI -> GatedInGaAsDetector

Physics is behavioral and calibrated (values + provenance in profiles/ingaas_spad.yaml).
The detector accumulates sifted clicks/errors across batches and exposes the running
QBER / gain / SKR via ctx.shared['metrics'].
"""
from __future__ import annotations

import numpy as np

from ..core.backends import FockBackend, QuantumStateBackend
from ..core.block import Block, SimContext, Timescale
from ..core.impairments import Afterpulsing, DarkCount, DeadTime, PhaseDriftOU
from ..core.signals import PulseBatch, SignalType
from .metrics import secret_fraction


class FaintPulseSource(Block):
    """Alice: weak coherent pulses with random bit + basis (signal intensity in M0)."""

    def __init__(self, name: str, mu_signal: float, rep_rate: float):
        super().__init__(name, Timescale.STATIC)
        self.mu_signal = float(mu_signal)
        self.rep_rate = float(rep_rate)
        self.ports_out = {"out": SignalType.OPTICAL}

    def process(self, batch: PulseBatch | None, ctx: SimContext) -> PulseBatch:
        n = int(ctx.shared["pulses"])
        rng = ctx.rng
        ctx.shared["rep_rate"] = self.rep_rate
        intensity = np.full(n, self.mu_signal)
        return PulseBatch(
            n=n,
            bit=rng.integers(0, 2, n),
            basis_a=rng.integers(0, 2, n),
            basis_b=rng.integers(0, 2, n),
            intensity=intensity,
            mu_eff=intensity.copy(),
        )


class FiberChannel(Block):
    """SMF G.652 attenuation: transmittance = 10^(-alpha*L/10)."""

    def __init__(self, name: str, length_km: float, alpha_db_km: float = 0.2):
        super().__init__(name, Timescale.STATIC)
        self.length_km = float(length_km)
        self.alpha_db_km = float(alpha_db_km)
        self.ports_in = {"in": SignalType.OPTICAL}
        self.ports_out = {"out": SignalType.OPTICAL}

    @property
    def transmittance(self) -> float:
        return 10.0 ** (-self.alpha_db_km * self.length_km / 10.0)

    def process(self, batch: PulseBatch, ctx: SimContext) -> PulseBatch:
        batch.mu_eff = batch.mu_eff * self.transmittance
        return batch


class BobAMZI(Block):
    """Bob's decoding asymmetric Mach-Zehnder interferometer.

    Carries an intrinsic visibility V0 and a slow phase drift (OU). The optical error
    rate is e_opt = 0.5*(1 - V0*cos(phi_resid)); phi_resid is the residual phase after
    an optional phase-lock control loop. Also applies Bob-side insertion loss.
    """

    def __init__(
        self,
        name: str,
        t_bob: float,
        visibility: float,
        drift: PhaseDriftOU,
        locked: bool = True,
        lock_gain: float = 0.9,
    ):
        super().__init__(name, Timescale.SLOW_DRIFT)
        self.t_bob = float(t_bob)
        self.V0 = float(visibility)
        self.drift = drift
        self.locked = locked
        self.lock_gain = float(lock_gain)
        self._est = 0.0  # phase-lock estimate (leaky integrator)
        # Optional externally-supplied per-tick phase trace (e.g. a measured drift log, or
        # a shared trajectory for engine validation). When set, it overrides the OU model.
        self.external_phase: np.ndarray | None = None
        self._tick = 0
        self.ports_in = {"in": SignalType.OPTICAL}
        self.ports_out = {"out": SignalType.OPTICAL}

    def step(self, ctx: SimContext) -> None:
        if self.external_phase is not None:
            phi = float(self.external_phase[min(self._tick, len(self.external_phase) - 1)])
            self._tick += 1
        else:
            phi = self.drift.step(ctx.dt, ctx.rng)
        if self.locked:
            self._est += self.lock_gain * (phi - self._est)
            resid = phi - self._est
        else:
            resid = phi
        e_opt = 0.5 * (1.0 - self.V0 * np.cos(resid))
        ctx.shared["e_opt"] = float(min(max(e_opt, 0.0), 0.5))
        ctx.shared["phase_resid"] = float(resid)

    def process(self, batch: PulseBatch, ctx: SimContext) -> PulseBatch:
        batch.mu_eff = batch.mu_eff * self.t_bob
        return batch

    def reset(self) -> None:
        self.drift.reset()
        self._est = 0.0
        self._tick = 0


class GatedInGaAsDetector(Block):
    """Gated InGaAs/InP single-photon detector with realistic impairments.

    Per pulse: a signal click (Fock backend, threshold model) competes with dark counts
    and (history-dependent) afterpulses; dead time reduces the live duty cycle at high
    rates. Clicks are sifted (basis match) and tagged as errors via the current optical
    error rate (signal clicks) or 50% (uncorrelated dark/afterpulse clicks).
    """

    def __init__(
        self,
        name: str,
        backend: QuantumStateBackend,
        eta_det: float,
        dark: DarkCount,
        after: Afterpulsing,
        deadtime: DeadTime,
    ):
        super().__init__(name, Timescale.STATEFUL)
        self.backend = backend
        self.eta_det = float(eta_det)
        self.dark = dark
        self.after = after
        self.deadtime = deadtime
        self.ports_in = {"in": SignalType.OPTICAL}
        self._recent_click_rate = 0.0
        self.reset()

    def reset(self) -> None:
        self.cum_total = 0
        self.cum_sifted_clicks = 0
        self.cum_sifted_errors = 0
        self._recent_click_rate = 0.0
        self.after.reset()

    def process(self, batch: PulseBatch, ctx: SimContext) -> PulseBatch:
        rng = ctx.rng
        n = batch.n
        rep_rate = ctx.shared.get("rep_rate", 1.0)

        # dead-time duty factor from recent count rate (negligible at metro rates)
        duty = self.deadtime.duty_factor(rep_rate * self._recent_click_rate)
        p_sig = self.backend.signal_click_prob(batch.mu_eff, self.eta_det) * duty
        p_noise = self.dark.p_dc + self.after.p_afterpulse()
        p_click = 1.0 - (1.0 - p_sig) * (1.0 - p_noise)

        clicked = rng.random(n) < p_click
        # attribute each click to signal vs noise (for the error model)
        p_is_noise = p_noise / (p_sig + p_noise + 1e-15)
        is_noise = clicked & (rng.random(n) < p_is_noise)
        is_signal = clicked & ~is_noise

        e_opt = ctx.shared.get("e_opt", 0.01)
        err = (is_signal & (rng.random(n) < e_opt)) | (is_noise & (rng.random(n) < 0.5))
        sifted = batch.basis_a == batch.basis_b

        # update history (afterpulse memory + dead-time rate)
        click_rate = float(clicked.mean())
        self.after.update(click_rate)
        self._recent_click_rate = 0.8 * self._recent_click_rate + 0.2 * click_rate

        # accumulate (sifted events only)
        sc = int(np.count_nonzero(clicked & sifted))
        se = int(np.count_nonzero(err & sifted))
        self.cum_total += n
        self.cum_sifted_clicks += sc
        self.cum_sifted_errors += se

        qber = self.cum_sifted_errors / self.cum_sifted_clicks if self.cum_sifted_clicks else 0.0
        gain = self.cum_sifted_clicks / self.cum_total if self.cum_total else 0.0  # per total pulse
        skr = rep_rate * gain * secret_fraction(qber)
        ctx.shared["metrics"] = {
            "qber": qber,
            "gain": gain,
            "skr": skr,
            "inst_qber": (se / sc if sc else 0.0),
        }

        batch.clicked, batch.error, batch.sifted = clicked, err, sifted
        return batch
