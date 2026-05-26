"""Secret-key-rate optimisation for 1-decoy BB84 — combines the channel model with the
Rusca 2018 finite-key bound and optimises the protocol parameters, as in the paper's
figures.

For a fixed privacy-amplification block size `n_Z` (Z-basis detections) at a given channel
loss, the achievable rate is

    SKR [Hz] = l * R / N_total ,   N_total = n_Z / (p_Z * (p_mu1*Q1 + p_mu2*Q2)) ,

i.e. the key length per the number of pulses needed to collect that block, times the
repetition rate R. Rusca optimise SKR over the intensities mu1, mu2, their probability
p_mu1, and the basis bias p_Z at every loss — `optimize_skr` does the same.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from .channel import ChannelParams, expected_decoy_counts, gain_qber
from .finite_key import DecoyCounts, KeyResult, secret_key_length


@dataclass
class SKRPoint:
    skr: float            # optimised secret-key rate (Hz)
    mu1: float
    mu2: float
    p_mu1: float
    p_Z: float
    n_total: float        # pulses needed to collect the n_Z block


def skr_for_params(
    loss_dB: float,
    n_Z_block: float,
    mu1: float,
    mu2: float,
    p_mu1: float,
    p_Z: float,
    *,
    rep_rate: float,
    params: ChannelParams,
    eps_sec: float,
    eps_cor: float,
    f_ec: float,
) -> tuple[float, float]:
    """(SKR in Hz, N_total) for one parameter set. Returns (0, inf) if infeasible."""
    if not (mu1 > mu2 > 0.0) or not (0.0 < p_mu1 < 1.0) or not (0.0 < p_Z < 1.0):
        return 0.0, float("inf")
    eta = params.eta_det * 10.0 ** (-loss_dB / 10.0)
    Q1, _ = gain_qber(mu1, eta, params.p_dc, params.e_d)
    Q2, _ = gain_qber(mu2, eta, params.p_dc, params.e_d)
    qZ = p_mu1 * Q1 + (1.0 - p_mu1) * Q2
    if qZ <= 0:
        return 0.0, float("inf")
    n_total = n_Z_block / (p_Z * qZ)
    counts = expected_decoy_counts(
        n_pulses=n_total, loss_dB=loss_dB, mu1=mu1, mu2=mu2,
        p_mu1=p_mu1, p_mu2=1.0 - p_mu1, p_Z=p_Z, params=params,
    )
    r = secret_key_length(counts, mu1=mu1, mu2=mu2, p_mu1=p_mu1, p_mu2=1.0 - p_mu1,
                          eps_sec=eps_sec, eps_cor=eps_cor, f_ec=f_ec)
    # Dead time caps the detection rate: duty = 1/(1 + R*Q_avg*tau). The engine path applies
    # this inside the detector already; here (analytic channel) we fold it in so both agree.
    q_avg = p_mu1 * Q1 + (1.0 - p_mu1) * Q2
    duty = 1.0 / (1.0 + rep_rate * q_avg * params.tau_dead) if params.tau_dead > 0 else 1.0
    return r.length * rep_rate / n_total * duty, n_total / duty


def optimize_skr(
    loss_dB: float,
    n_Z_block: float,
    *,
    rep_rate: float = 1e9,
    params: ChannelParams | None = None,
    eps_sec: float = 1e-9,
    eps_cor: float = 1e-15,
    f_ec: float = 1.2,
    n_restarts: int = 6,
    seed: int = 0,
) -> SKRPoint:
    """Maximise SKR over (mu1, mu2, p_mu1, p_Z) at the given loss and block size.

    Parameterised as mu1, r=mu2/mu1 in (0,1), p_mu1, p_Z to keep mu1>mu2 automatically.
    Multi-start L-BFGS-B; returns the best feasible point (SKR=0 if none)."""
    params = params or ChannelParams()
    rng = np.random.default_rng(seed)

    def neg_skr(x):
        mu1, ratio, p_mu1, p_Z = x
        mu2 = ratio * mu1
        skr, _ = skr_for_params(loss_dB, n_Z_block, mu1, mu2, p_mu1, p_Z,
                                rep_rate=rep_rate, params=params, eps_sec=eps_sec,
                                eps_cor=eps_cor, f_ec=f_ec)
        return -skr

    bounds = [(0.05, 0.9), (0.02, 0.9), (0.5, 0.98), (0.5, 0.999)]
    best = None
    starts = [np.array([0.5, 0.3, 0.7, 0.7])]
    for _ in range(n_restarts - 1):
        starts.append(np.array([rng.uniform(*b) for b in bounds]))
    for x0 in starts:
        res = minimize(neg_skr, x0, method="L-BFGS-B", bounds=bounds)
        if best is None or res.fun < best.fun:
            best = res

    mu1, ratio, p_mu1, p_Z = best.x
    mu2 = ratio * mu1
    skr, n_total = skr_for_params(loss_dB, n_Z_block, mu1, mu2, p_mu1, p_Z,
                                  rep_rate=rep_rate, params=params, eps_sec=eps_sec,
                                  eps_cor=eps_cor, f_ec=f_ec)
    return SKRPoint(skr=max(0.0, skr), mu1=mu1, mu2=mu2, p_mu1=p_mu1, p_Z=p_Z, n_total=n_total)


def skr_from_rates(
    rates: dict,
    *,
    mu1: float,
    mu2: float,
    p_mu1: float,
    p_Z: float,
    n_Z_block: float,
    rep_rate: float = 1e9,
    eps_sec: float = 1e-9,
    eps_cor: float = 1e-15,
    f_ec: float = 1.16,
) -> tuple[float, KeyResult]:
    """Finite-key SKR from ENGINE-MEASURED per-(basis,intensity) rates.

    `rates` is the dict from DecoyBB84Detector.rates() (Q_Z1.. E_X2). Because the batched
    engine subsamples pulses, we use it to estimate the *rates* (gains/QBERs, with all real
    impairments folded in) and then evaluate the finite-key bound at the user's absolute
    privacy-amplification block size `n_Z_block`. Returns (SKR Hz, KeyResult)."""
    qZ = p_mu1 * rates["Q_Z1"] + (1.0 - p_mu1) * rates["Q_Z2"]
    if qZ <= 0:
        return 0.0, KeyResult(0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, False)
    n_total = n_Z_block / (p_Z * qZ)

    NZ1 = n_total * p_Z * p_mu1
    NZ2 = n_total * p_Z * (1.0 - p_mu1)
    NX1 = n_total * (1.0 - p_Z) * p_mu1
    NX2 = n_total * (1.0 - p_Z) * (1.0 - p_mu1)
    c = DecoyCounts(
        nZ1=NZ1 * rates["Q_Z1"], nZ2=NZ2 * rates["Q_Z2"],
        mZ1=NZ1 * rates["Q_Z1"] * rates["E_Z1"], mZ2=NZ2 * rates["Q_Z2"] * rates["E_Z2"],
        nX1=NX1 * rates["Q_X1"], nX2=NX2 * rates["Q_X2"],
        mX1=NX1 * rates["Q_X1"] * rates["E_X1"], mX2=NX2 * rates["Q_X2"] * rates["E_X2"],
    )
    r = secret_key_length(c, mu1=mu1, mu2=mu2, p_mu1=p_mu1, p_mu2=1.0 - p_mu1,
                          eps_sec=eps_sec, eps_cor=eps_cor, f_ec=f_ec)
    return r.length * rep_rate / n_total, r
