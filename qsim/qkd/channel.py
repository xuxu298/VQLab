"""Analytic decoy-BB84 channel model — expected per-(basis, intensity) counts.

Standard weak-coherent-pulse + threshold-detector model (Ma et al., PRA 72, 012326 (2005)),
used by the decoy-state literature (incl. Rusca 2018) to *simulate* expected statistics:

    gain    Q_mu = Y0 + 1 - exp(-eta * mu)
    QBER    E_mu = (e0 * Y0 + e_d * (1 - exp(-eta * mu))) / Q_mu

with eta the end-to-end single-photon transmittance (channel loss x detector efficiency),
Y0 the background/dark yield per pulse, e0 = 1/2 (random error on background clicks), and
e_d the intrinsic optical/misalignment error.

This is an *expected-value* model (no Monte-Carlo noise). It feeds the finite-key estimator
two ways: (1) to unit-test the estimator, (2) to reproduce Rusca's published SKR figure.
It is also the analytic reference the multi-rate engine's simulated counts can be checked
against — the same role the brute-force reference played for M0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .finite_key import DecoyCounts


@dataclass
class ChannelParams:
    eta_det: float = 0.5      # detector efficiency
    fiber_alpha: float = 0.2  # dB/km
    p_dc: float = 1e-7        # dark-count probability per pulse, per detector
    e_d: float = 0.005        # intrinsic optical/misalignment error (e_opt)
    tau_dead: float = 0.0     # detector dead time (s); 0 = ignore (caps the count rate)


def gain_qber(mu: float, eta: float, p_dc: float, e_d: float) -> tuple[float, float]:
    """(gain Q_mu, QBER E_mu) for intensity mu at end-to-end transmittance eta."""
    Y0 = 2.0 * p_dc                       # two BB84 detectors -> background yield
    Q = Y0 + 1.0 - math.exp(-eta * mu)
    E = (0.5 * Y0 + e_d * (1.0 - math.exp(-eta * mu))) / Q
    return Q, E


def expected_decoy_counts(
    *,
    n_pulses: float,
    loss_dB: float,
    mu1: float,
    mu2: float,
    p_mu1: float,
    p_mu2: float,
    p_Z: float,
    params: ChannelParams | None = None,
) -> DecoyCounts:
    """Expected sifted counts for `n_pulses` total, at channel loss `loss_dB`.

    `loss_dB` is the link loss before the detector; the detector efficiency in `params` is
    folded in. Counts are split by basis (p_Z) and intensity (p_mu1/p_mu2), and sifting
    keeps the matched-basis fraction (already reflected: n_pulses is the post-sift budget
    per basis when p_Z is applied)."""
    p = params or ChannelParams()
    eta = p.eta_det * 10.0 ** (-loss_dB / 10.0)
    Q1, E1 = gain_qber(mu1, eta, p.p_dc, p.e_d)
    Q2, E2 = gain_qber(mu2, eta, p.p_dc, p.e_d)

    def basis(pB: float):
        N1 = n_pulses * pB * p_mu1
        N2 = n_pulses * pB * p_mu2
        return N1 * Q1, N2 * Q2, N1 * Q1 * E1, N2 * Q2 * E2

    nZ1, nZ2, mZ1, mZ2 = basis(p_Z)
    nX1, nX2, mX1, mX2 = basis(1.0 - p_Z)
    return DecoyCounts(nZ1, nZ2, mZ1, mZ2, nX1, nX2, mX1, mX2)
