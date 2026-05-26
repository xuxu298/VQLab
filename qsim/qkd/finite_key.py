"""Rusca et al. 2018 — finite-key analysis of the 1-decoy-state BB84 protocol.

Reference: D. Rusca, A. Boaron, F. Grünenfelder, A. Martin, H. Zbinden,
"Finite-key analysis for the 1-decoy state QKD protocol", Appl. Phys. Lett. 112, 171104
(2018); arXiv:1801.03443. This is the protocol named in docs/01 §0.

This module is the security-critical CORE of M1: a *pure* function from observed counts to
a composably-secure secret-key length. It knows nothing about the simulator — it takes the
per-(basis, intensity) sifted detection and error counts (from the engine, or from an
analytic channel model, or from a real device) and returns the proven key length.

Protocol recap. Alice sends weak coherent pulses, each with a basis (Z = key, with prob
p_Z; X = test) and an intensity (signal mu1 or decoy mu2, mu1 > mu2 > 0). After sifting we
observe, per basis b and intensity k:
    n_{b,k} = detections,   m_{b,k} = errors.
The 1-decoy method bounds the vacuum (s_{Z,0}) and single-photon (s_{Z,1}) contributions to
the Z-basis key and the single-photon phase error (phi_Z) from the X basis, then:

    l = s_{Z,0}^l + s_{Z,1}^l (1 - h(phi_Z^u)) - lambda_EC
        - 6 log2(19/eps_sec) - log2(2/eps_cor).

Two implementation choices are flagged where the paper text we could verify was ambiguous;
both are resolved by reproducing the paper's published SKR-vs-loss figure (see
demos/m1_rusca_validation.py):
  * `s_{Z,0}^u` is evaluated for BOTH intensities and the (valid, tighter) minimum is taken.
  * the Hoeffding deviation uses natural log (standard for the Hoeffding/Chernoff bound),
    while entropies and the key formula use log2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .metrics import binary_entropy as _h


@dataclass
class DecoyCounts:
    """Observed sifted counts per basis (Z=key, X=test) and intensity (1=signal, 2=decoy)."""

    nZ1: float   # Z-basis detections at mu1
    nZ2: float   # Z-basis detections at mu2
    mZ1: float   # Z-basis errors at mu1
    mZ2: float   # Z-basis errors at mu2
    nX1: float   # X-basis detections at mu1
    nX2: float
    mX1: float
    mX2: float


@dataclass
class KeyResult:
    length: float          # secret-key length l (bits), clamped to >= 0
    sZ0_l: float           # lower bound, vacuum events in Z
    sZ1_l: float           # lower bound, single-photon events in Z
    phiZ_u: float          # upper bound, single-photon phase error in Z
    lambda_EC: float       # error-correction leakage
    nZ: float
    qberZ: float
    feasible: bool         # False if the bounds degenerated (l forced to 0)


def _tau(n: int, mu1: float, mu2: float, p1: float, p2: float) -> float:
    """tau_n = sum_k p_k e^{-k} k^n / n!  — prob. Alice emits an n-photon state."""
    fact = math.factorial(n)
    return (p1 * math.exp(-mu1) * mu1 ** n + p2 * math.exp(-mu2) * mu2 ** n) / fact


def secret_key_length(
    c: DecoyCounts,
    *,
    mu1: float,
    mu2: float,
    p_mu1: float,
    p_mu2: float,
    eps_sec: float = 1e-9,
    eps_cor: float = 1e-15,
    f_ec: float = 1.16,
) -> KeyResult:
    """Composably-secure secret-key length for 1-decoy BB84 (Rusca 2018).

    `p_mu1`, `p_mu2` are the intensity-selection probabilities (sum to 1). `eps_sec`,
    `eps_cor` are the secrecy and correctness parameters. `f_ec` is the error-correction
    efficiency used for the leakage estimate lambda_EC = f_ec * nZ * h(QBER_Z).
    """
    if not (mu1 > mu2 > 0.0):
        raise ValueError("require mu1 > mu2 > 0 (1-decoy constraint)")

    tau0 = _tau(0, mu1, mu2, p_mu1, p_mu2)
    tau1 = _tau(1, mu1, mu2, p_mu1, p_mu2)

    nZ = c.nZ1 + c.nZ2
    mZ = c.mZ1 + c.mZ2
    nX = c.nX1 + c.nX2
    mX = c.mX1 + c.mX2

    # eps_sec = 19 * eps  (all internal statistical terms set equal); eps1 = eps2 = eps.
    eps = eps_sec / 19.0
    qberZ = mZ / nZ if nZ > 0 else 0.0

    if nZ <= 0 or nX <= 0:
        return KeyResult(0.0, 0.0, 0.0, 0.5, 0.0, nZ, qberZ, False)

    # --- Hoeffding-corrected counts (deviation uses TOTAL counts in the basis) ----------
    def dev(total: float, e: float) -> float:
        return math.sqrt(0.5 * total * math.log(1.0 / e)) if total > 0 else 0.0

    dnZ, dmZ = dev(nZ, eps), dev(mZ, eps)
    dnX, dmX = dev(nX, eps), dev(mX, eps)

    def npm(n_bk: float, mu: float, p: float, d: float, sign: int) -> float:
        return (math.exp(mu) / p) * (n_bk + sign * d)

    # Z basis
    nZ1_p = npm(c.nZ1, mu1, p_mu1, dnZ, +1)
    nZ2_m = npm(c.nZ2, mu2, p_mu2, dnZ, -1)
    # X basis
    nX1_p = npm(c.nX1, mu1, p_mu1, dnX, +1)
    nX2_m = npm(c.nX2, mu2, p_mu2, dnX, -1)
    mX1_p = npm(c.mX1, mu1, p_mu1, dmX, +1)
    mX2_m = npm(c.mX2, mu2, p_mu2, dmX, -1)

    # --- vacuum bounds (Z) --------------------------------------------------------------
    sZ0_l = max(0.0, tau0 / (mu1 - mu2) * (mu1 * nZ2_m - mu2 * nZ1_p))

    # upper bound on vacuum: valid for either intensity; take the tighter (min).
    def sZ0u_for(m_bk: float, mu: float, p: float) -> float:
        return 2.0 * (tau0 * (math.exp(mu) / p) * (m_bk + dmZ) + dnZ)
    sZ0_u = min(sZ0u_for(c.mZ1, mu1, p_mu1), sZ0u_for(c.mZ2, mu2, p_mu2))

    # --- single-photon lower bound (Z and X share the same estimator form) --------------
    def s1_lower(n1_p: float, n2_m: float, s0_u: float) -> float:
        val = (tau1 * mu1 / (mu2 * (mu1 - mu2))) * (
            n2_m
            - (mu2 ** 2 / mu1 ** 2) * n1_p
            - (mu1 ** 2 - mu2 ** 2) / mu1 ** 2 * (s0_u / tau0)
        )
        return max(0.0, val)

    sZ1_l = s1_lower(nZ1_p, nZ2_m, sZ0_u)

    # For the X basis we need s_{X,1}^l (and its own vacuum upper bound).
    def sX0u_for(m_bk: float, mu: float, p: float) -> float:
        return 2.0 * (tau0 * (math.exp(mu) / p) * (m_bk + dmX) + dnX)
    sX0_u = min(sX0u_for(c.mX1, mu1, p_mu1), sX0u_for(c.mX2, mu2, p_mu2))
    sX1_l = s1_lower(nX1_p, nX2_m, sX0_u)

    # --- single-photon phase error (from X basis) ---------------------------------------
    vX1_u = tau1 / (mu1 - mu2) * (mX1_p - mX2_m)

    if sZ1_l <= 0.0 or sX1_l <= 0.0:
        lambda_EC = f_ec * nZ * _h(qberZ)
        return KeyResult(0.0, sZ0_l, sZ1_l, 0.5, lambda_EC, nZ, qberZ, False)

    ratio = vX1_u / sX1_l
    ratio = min(max(ratio, 0.0), 0.5)
    phiZ_u = min(0.5, ratio + _gamma(eps_sec, ratio, sZ1_l, sX1_l))

    # --- key length ---------------------------------------------------------------------
    lambda_EC = f_ec * nZ * _h(qberZ)
    length = (
        sZ0_l
        + sZ1_l * (1.0 - _h(phiZ_u))
        - lambda_EC
        - 6.0 * math.log2(19.0 / eps_sec)
        - math.log2(2.0 / eps_cor)
    )
    feasible = length > 0.0
    return KeyResult(max(0.0, length), sZ0_l, sZ1_l, phiZ_u, lambda_EC, nZ, qberZ, feasible)


def _gamma(a: float, b: float, c: float, d: float) -> float:
    """gamma(a,b,c,d) from Rusca 2018 — the finite-size correction on the phase error.

    a = eps_sec, b = vX1_u/sX1_l, c = sZ1_l, d = sX1_l.
    """
    if c <= 0 or d <= 0 or not (0.0 < b < 1.0):
        return 0.5
    inner = ((c + d) / (c * d * (1.0 - b) * b)) * (21.0 ** 2 / a ** 2)
    if inner <= 0:
        return 0.5
    val = ((c + d) * (1.0 - b) * b) / (c * d * math.log(2.0)) * math.log2(inner)
    return math.sqrt(val) if val > 0 else 0.0
