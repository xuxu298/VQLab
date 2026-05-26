"""Validation harness: batched multi-rate engine vs the brute-force per-pulse reference.

This is the M0 make-or-break check (spec §14 risk #1). It runs the cheap batched engine and
the expensive sequential `bruteforce` on identical parameters and compares the aggregate
QBER and gain, with a principled binomial confidence interval, plus a speed comparison.

Two regimes:
  * **static** (drift off) — isolates the statistical-aggregation + mean-field-afterpulse +
    dead-time-duty approximations.
  * **drift** (OU on, unlocked) — isolates the freeze-slow-state-per-batch approximation:
    the batched engine holds the phase constant for a whole `dt_slow` batch while the
    reference walks it every gate; the time-averaged QBER must still agree.

CRITICAL: the two engines are matched by **physical duration**, not sample count. The
batched engine subsamples pulses but advances real time by `dt_slow` per tick; the
reference simulates every gate at `1/rep_rate`. With slow drift, QBER depends on how far
the phase has wandered — i.e. on elapsed physical time — so both must cover the same
`seconds` window for the comparison to be apples-to-apples.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from .bruteforce import bruteforce_from_profile, BruteForceResult
from .reference import build_bb84_slice, load_default_profile


@dataclass
class BatchedResult:
    qber: float
    gain: float
    skr: float
    sifted_clicks: int
    n_pulses: int
    elapsed_s: float
    pulses_per_s: float


def make_ou_path(n: int, dt: float, theta: float, sigma: float,
                 rng: np.random.Generator) -> np.ndarray:
    """A single Ornstein-Uhlenbeck phase trajectory of `n` samples at step `dt`, starting
    at 0. Used to drive both engines with one shared trajectory in the drift validation."""
    phi = np.empty(n)
    x = 0.0
    s = sigma * math.sqrt(dt)
    z = rng.standard_normal(n)
    for i in range(n):
        x += -theta * x * dt + s * z[i]
        phi[i] = x
    return phi


def run_batched(
    profile,
    *,
    length_km: float,
    n_ticks: int,
    dt_slow: float,
    pulses_per_tick: int,
    rng: np.random.Generator,
    drift: bool,
    external_phase: np.ndarray | None = None,
) -> BatchedResult:
    """Run the batched engine for `n_ticks` of the `dt_slow` clock. drift=False pins the
    AMZI phase (static); drift=True leaves the OU walk on with the phase lock OFF. If
    `external_phase` (per-tick) is given, the AMZI replays it instead of stepping its own
    OU — so the batched engine and the reference share one trajectory."""
    _g, sched, det, amzi = build_bb84_slice(profile, length_km=length_km, locked=False)
    if not drift:
        amzi.drift.sigma = 0.0
        amzi.drift.theta = 0.0
        amzi.drift.phi = 0.0
    if external_phase is not None:
        amzi.external_phase = external_phase
    t0 = time.perf_counter()
    sched.run(n_ticks=n_ticks, dt_slow=dt_slow, pulses_per_tick=pulses_per_tick, rng=rng)
    elapsed = time.perf_counter() - t0
    qber = det.cum_sifted_errors / det.cum_sifted_clicks if det.cum_sifted_clicks else 0.0
    gain = det.cum_sifted_clicks / det.cum_total if det.cum_total else 0.0
    from .metrics import secret_fraction
    skr = profile.value("rep_rate") * gain * secret_fraction(qber)
    return BatchedResult(
        qber=qber,
        gain=gain,
        skr=skr,
        sifted_clicks=det.cum_sifted_clicks,
        n_pulses=det.cum_total,
        elapsed_s=elapsed,
        pulses_per_s=(det.cum_total / elapsed if elapsed > 0 else float("inf")),
    )


def _binom_se(p: float, n: int) -> float:
    return math.sqrt(max(p * (1.0 - p), 0.0) / n) if n > 0 else float("inf")


@dataclass
class Comparison:
    length_km: float
    drift: bool
    batched: BatchedResult
    bruteforce: BruteForceResult
    dq: float            # |QBER_batched - QBER_bruteforce|
    qber_ci: float       # combined ~1-sigma binomial CI on the QBER difference
    dgain_rel: float     # relative gain difference
    gain_ci_rel: float   # combined ~1-sigma relative CI on the gain difference
    speedup: float       # batched pulses/s ÷ bruteforce gates/s

    @property
    def qber_sigmas(self) -> float:
        return self.dq / self.qber_ci if self.qber_ci > 0 else float("inf")

    @property
    def gain_sigmas(self) -> float:
        return self.dgain_rel / self.gain_ci_rel if self.gain_ci_rel > 0 else float("inf")


def compare(
    *,
    length_km: float,
    drift: bool,
    seconds: float,
    dt_slow: float = 1e-4,
    pulses_per_tick: int = 20_000,
    seed: int = 1,
    profile=None,
) -> Comparison:
    """Run both engines over the SAME physical `seconds` window and compare.

    The brute-force resolves every gate (`seconds * rep_rate` of them); the batched engine
    takes `seconds / dt_slow` ticks, each a subsampled batch of `pulses_per_tick` pulses.
    """
    profile = profile or load_default_profile()
    rep_rate = profile.value("rep_rate")
    n_gates = max(1, round(seconds * rep_rate))
    n_ticks = max(1, round(seconds / dt_slow))
    gates_per_tick = max(1, round(dt_slow * rep_rate))

    # For the drift regime, build ONE fine OU trajectory and drive both engines with it so
    # trajectory variance cancels and the comparison isolates the freezing approximation.
    phi_path = None
    ext_phase = None
    if drift:
        dt_gate = 1.0 / rep_rate
        phi_path = make_ou_path(
            n_gates, dt_gate, profile.value("drift_theta"), profile.value("drift_sigma"),
            np.random.default_rng(seed + 7),
        )
        ext_phase = phi_path[:: gates_per_tick][:n_ticks]   # frozen value per batch

    b = run_batched(
        profile,
        length_km=length_km,
        n_ticks=n_ticks,
        dt_slow=dt_slow,
        pulses_per_tick=pulses_per_tick,
        rng=np.random.default_rng(seed),
        drift=drift,
        external_phase=ext_phase,
    )
    bf = bruteforce_from_profile(
        profile, length_km=length_km, n_gates=n_gates,
        rng=np.random.default_rng(seed + 1000), drift=drift, phi_path=phi_path,
    )

    dq = abs(b.qber - bf.qber)
    qber_ci = math.hypot(_binom_se(b.qber, b.sifted_clicks), _binom_se(bf.qber, bf.sifted_clicks))

    dgain_rel = abs(b.gain - bf.gain) / bf.gain if bf.gain else float("inf")
    gain_ci_rel = math.hypot(
        _binom_se(b.gain, b.n_pulses) / b.gain if b.gain else float("inf"),
        _binom_se(bf.gain, bf.n_gates) / bf.gain if bf.gain else float("inf"),
    )
    speedup = b.pulses_per_s / bf.gates_per_s if bf.gates_per_s else float("inf")

    return Comparison(
        length_km=length_km,
        drift=drift,
        batched=b,
        bruteforce=bf,
        dq=dq,
        qber_ci=qber_ci,
        dgain_rel=dgain_rel,
        gain_ci_rel=gain_ci_rel,
        speedup=speedup,
    )
