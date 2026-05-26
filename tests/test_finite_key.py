"""Tests for the Rusca 2018 1-decoy finite-key estimator (qsim/qkd/finite_key.py).

These check the security bound has the right *shape and limits*. Quantitative validation
against the paper's published SKR-vs-loss figure lives in demos/m1_rusca_validation.py
(it also resolves the two documented implementation ambiguities).
"""
import math

import pytest

from qsim.qkd.channel import expected_decoy_counts
from qsim.qkd.finite_key import DecoyCounts, secret_key_length

MU1, MU2, P1, P2, PZ = 0.5, 0.1, 0.7, 0.3, 0.5


def skl(n_pulses, loss_dB, **kw):
    c = expected_decoy_counts(n_pulses=n_pulses, loss_dB=loss_dB, mu1=MU1, mu2=MU2,
                              p_mu1=P1, p_mu2=P2, p_Z=PZ)
    return secret_key_length(c, mu1=MU1, mu2=MU2, p_mu1=P1, p_mu2=P2, **kw)


def test_requires_valid_intensities():
    c = DecoyCounts(*([1.0] * 8))
    with pytest.raises(ValueError):
        secret_key_length(c, mu1=0.1, mu2=0.5, p_mu1=0.5, p_mu2=0.5)   # mu1 < mu2
    with pytest.raises(ValueError):
        secret_key_length(c, mu1=0.5, mu2=0.0, p_mu1=0.5, p_mu2=0.5)   # mu2 = 0


def test_bounds_are_physical():
    r = skl(1e9, 10.0)
    assert 0.0 <= r.sZ0_l
    assert 0.0 <= r.sZ1_l <= r.nZ            # single-photon events can't exceed detections
    assert 0.0 <= r.phiZ_u <= 0.5
    assert r.length >= 0.0
    assert r.feasible


def test_positive_key_low_loss_large_block():
    r = skl(1e10, 0.0)
    assert r.feasible and r.length > 0
    assert 0.4 < r.length / r.nZ < 0.9       # healthy single-photon secret fraction


def test_key_collapses_at_high_loss():
    # Far past where the single-photon phase error crosses the threshold.
    r = skl(1e10, 55.0)
    assert r.length == 0.0 and not r.feasible


def test_key_decreases_with_loss():
    losses = [0.0, 10.0, 20.0, 30.0]
    fracs = [skl(1e10, L).length / skl(1e10, L).nZ for L in losses]
    assert all(a > b for a, b in zip(fracs, fracs[1:]))   # strictly decreasing fraction


def test_finite_size_penalty_shrinks_with_block_size():
    # Larger blocks -> smaller statistical penalty -> higher key fraction, converging up.
    fracs = [skl(N, 10.0).length / skl(N, 10.0).nZ for N in (1e7, 1e8, 1e9, 1e10, 1e11)]
    assert all(a < b + 1e-12 for a, b in zip(fracs, fracs[1:]))   # monotonic non-decreasing
    assert fracs[-1] - fracs[0] > 0.02                            # penalty is real at 1e7


def test_block_too_small_gives_no_key():
    # A tiny block cannot overcome the fixed -6 log2(19/eps) - log2(2/eps_cor) cost.
    r = skl(5e3, 0.0)
    assert r.length == 0.0


def test_asymptotic_fraction_converges():
    # As block -> very large, l/nZ approaches a stable asymptote (finite-size terms vanish).
    f_big = skl(1e13, 10.0).length / skl(1e13, 10.0).nZ
    f_huge = skl(1e15, 10.0).length / skl(1e15, 10.0).nZ
    assert abs(f_huge - f_big) < 0.01
