"""Brute-force per-pulse QKD reference — the ground truth that validates the multi-rate
engine (spec §14 risk #1, the make-or-break: *"benchmark against a brute-force reference
on a small case"*).

This module deliberately does the EXPENSIVE thing the batched engine avoids: it simulates
every detector gate **sequentially**, resolving the genuinely sequential physics that the
batched engine replaces with a frozen-per-batch mean field:

  * **Afterpulsing** as a real decaying trap-population memory — a click injects carriers
    that raise the *next* gates' afterpulse probability (non-Markovian), instead of a
    per-batch average click rate.
  * **Dead time** as actual blocked gates after each click, instead of a duty-cycle factor.
  * **OU phase drift** updated *every gate*, instead of frozen for a whole batch.

It is calibrated to the **same steady-state means** as the batched models (see
`_afterpulse_kick`), so agreement isolates exactly the question M0 must answer: does
freezing the slow state per batch + replacing per-event correlations with their mean +
accumulating statistically preserve the aggregate QBER and gain?

Scope (honesty, spec §7): this validates the *aggregation approximation* against a
per-event simulation of the **same** behavioral physics. It does NOT validate the physics
itself against reality — that is M1 (compare to a published experiment).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from .metrics import secret_fraction


@dataclass
class BruteForceResult:
    qber: float
    gain: float              # sifted clicks / total gates
    skr: float               # rep_rate * gain * secret_fraction(qber)
    sifted_clicks: int
    sifted_errors: int
    n_gates: int
    elapsed_s: float
    gates_per_s: float


def _afterpulse_kick(amp: float, beta: float) -> float:
    """Per-click afterpulse contribution `kappa` such that the brute-force trap model has
    the SAME steady-state mean afterpulse probability as the batched mean-field model.

    Batched model:   p_ap = amp * click_rate   (mean-field over the recent click rate).
    Brute-force trap: mem_{i+1} = beta*mem_i + click_i ,  p_ap_i = kappa * mem_i .
    At steady state E[mem] = E[click]/(1-beta) = click_rate/(1-beta), so
        E[p_ap] = kappa * click_rate / (1-beta).
    Matching the two means  =>  kappa = amp * (1 - beta).
    """
    return amp * (1.0 - beta)


def run_bruteforce(
    *,
    n_gates: int,
    mu_signal: float,
    fiber_T: float,
    bob_T: float,
    eta_det: float,
    p_dark: float,
    afterpulse_amp: float,
    dead_time_s: float,
    rep_rate: float,
    visibility: float,
    drift_theta: float,
    drift_sigma: float,
    rng: np.random.Generator,
    tau_ap_gates: float = 100.0,
    phi_path: np.ndarray | None = None,
) -> BruteForceResult:
    """Sequentially simulate `n_gates` detector gates and return aggregate QBER/gain/SKR.

    Parameters mirror the batched slice exactly (intensities already folded so that
    `mu_eff = mu_signal * fiber_T * bob_T`). `drift_sigma=0` gives a static phase (isolates
    the statistical/mean-field approximation); `drift_sigma>0` drives a per-gate OU walk
    (isolates the freeze-slow-state-per-batch approximation). If `phi_path` (length
    `n_gates`) is supplied, the per-gate phase is taken from it instead of an internal OU
    walk — used to drive this reference and the batched engine with one shared trajectory,
    so trajectory variance cancels and only the freezing approximation remains.
    """
    dt_gate = 1.0 / rep_rate
    mu_eff = mu_signal * fiber_T * bob_T
    p_sig = 1.0 - math.exp(-mu_eff * eta_det)

    beta = math.exp(-1.0 / tau_ap_gates)         # trap decay per gate
    kappa = _afterpulse_kick(afterpulse_amp, beta)
    dead_gates = int(round(dead_time_s * rep_rate))

    V = visibility
    use_path = phi_path is not None
    drift_on = (drift_sigma > 0.0) and not use_path
    sig_step = drift_sigma * math.sqrt(dt_gate)

    # Pre-draw randoms in bulk (the sequential dependency is the trap/dead-time state,
    # not the random draws, so we can vectorise the RNG and keep a tight Python loop).
    u_click = rng.random(n_gates)
    u_attr = rng.random(n_gates)
    u_err = rng.random(n_gates)
    sift = rng.random(n_gates) < 0.5             # Alice/Bob basis match (kept after sifting)
    z = rng.standard_normal(n_gates) if drift_on else None

    phi = 0.0
    mem = 0.0
    dead_until = -1
    cum_sift_clicks = 0
    cum_sift_errors = 0

    t0 = time.perf_counter()
    for i in range(n_gates):
        if use_path:
            phi = phi_path[i]
        elif drift_on:
            phi += -drift_theta * phi * dt_gate + sig_step * z[i]
        # residual optical error at this gate's instantaneous phase
        e_opt = 0.5 * (1.0 - V * math.cos(phi))
        if e_opt < 0.0:
            e_opt = 0.0
        elif e_opt > 0.5:
            e_opt = 0.5

        if i <= dead_until:
            mem *= beta                # detector dead: no click possible; trap still decays
            continue

        p_ap = kappa * mem
        p_noise = p_dark + p_ap
        p_click = 1.0 - (1.0 - p_sig) * (1.0 - p_noise)

        clicked = u_click[i] < p_click
        mem *= beta                    # decay, then kick on a click
        if clicked:
            mem += 1.0
            dead_until = i + dead_gates
            p_is_noise = p_noise / (p_sig + p_noise + 1e-15)
            if u_attr[i] < p_is_noise:
                err = u_err[i] < 0.5            # dark/afterpulse click: uncorrelated -> 50%
            else:
                err = u_err[i] < e_opt          # genuine signal click: optical error rate
            if sift[i]:
                cum_sift_clicks += 1
                if err:
                    cum_sift_errors += 1
    elapsed = time.perf_counter() - t0

    qber = cum_sift_errors / cum_sift_clicks if cum_sift_clicks else 0.0
    gain = cum_sift_clicks / n_gates if n_gates else 0.0
    skr = rep_rate * gain * secret_fraction(qber)
    return BruteForceResult(
        qber=qber,
        gain=gain,
        skr=skr,
        sifted_clicks=cum_sift_clicks,
        sifted_errors=cum_sift_errors,
        n_gates=n_gates,
        elapsed_s=elapsed,
        gates_per_s=(n_gates / elapsed if elapsed > 0 else float("inf")),
    )


def bruteforce_from_profile(profile, *, length_km: float, n_gates: int,
                            rng: np.random.Generator, drift: bool = False,
                            phi_path: np.ndarray | None = None) -> BruteForceResult:
    """Convenience: build a brute-force run from the same CalibrationProfile the batched
    slice uses, so both engines share identical parameters. If `phi_path` is given it
    drives the per-gate phase (shared-trajectory validation); otherwise an internal OU walk
    runs when `drift` is True."""
    fiber_T = 10.0 ** (-profile.value("fiber_alpha") * length_km / 10.0)
    return run_bruteforce(
        n_gates=n_gates,
        mu_signal=profile.value("mu_signal"),
        fiber_T=fiber_T,
        bob_T=profile.value("bob_transmittance"),
        eta_det=profile.value("eta_det"),
        p_dark=profile.value("p_dark"),
        afterpulse_amp=profile.value("afterpulse_amp"),
        dead_time_s=profile.value("dead_time"),
        rep_rate=profile.value("rep_rate"),
        visibility=profile.value("visibility"),
        drift_theta=profile.value("drift_theta"),
        drift_sigma=profile.value("drift_sigma") if drift else 0.0,
        rng=rng,
        phi_path=phi_path,
    )
