"""End-to-end M1: the multi-rate engine drives the real Rusca finite-key bound.

The decoy source + sifting detector accumulate per-(basis, intensity) counts under the full
M0 impairment set (afterpulse, phase drift, dead time); skr_from_rates evaluates the
finite-key SKR at a chosen privacy-amplification block size. We check the engine's measured
gains cross-check the analytic channel, and that the resulting SKR behaves correctly.
"""
import numpy as np
import pytest

from qsim.qkd.channel import gain_qber
from qsim.qkd.keyrate import skr_from_rates
from qsim.qkd.reference import build_decoy_bb84, load_default_profile

PROF = load_default_profile()
MU1, MU2 = PROF.value("mu1"), PROF.value("mu2")
P1, PZ = PROF.value("p_mu1"), PROF.value("p_Z")
REP = PROF.value("rep_rate")


def run(length_km, ticks=300, pulses=200_000, seed=1):
    g, sched, det, _amzi = build_decoy_bb84(PROF, length_km=length_km, locked=True)
    sched.run(n_ticks=ticks, dt_slow=1e-3, pulses_per_tick=pulses,
              rng=np.random.default_rng(seed))
    return det.rates()


@pytest.fixture(scope="module")
def rates25():
    return run(25.0)


def test_signal_gain_exceeds_decoy(rates25):
    # Brighter signal intensity must yield a higher gain than the decoy, in both bases.
    assert rates25["Q_Z1"] > rates25["Q_Z2"] > 0
    assert rates25["Q_X1"] > rates25["Q_X2"] > 0
    assert rates25["clicks"] > 10_000


def test_engine_gain_cross_checks_analytic(rates25):
    # End-to-end transmittance: detector eff x fiber x Bob optics. The engine adds
    # afterpulse/dark on top, so it should be >= the dark-light analytic gain, and close.
    fiberT = 10 ** (-PROF.value("fiber_alpha") * 25.0 / 10)
    eta = PROF.value("eta_det") * fiberT * PROF.value("bob_transmittance")
    Q1a, _ = gain_qber(MU1, eta, PROF.value("p_dark"), 0.0)
    assert rates25["Q_Z1"] == pytest.approx(Q1a, rel=0.05)


def test_positive_skr_and_distance_dependence():
    r25, r50 = run(25.0), run(50.0)
    skr25, kr25 = skr_from_rates(r25, mu1=MU1, mu2=MU2, p_mu1=P1, p_Z=PZ,
                                 n_Z_block=1e9, rep_rate=REP)
    skr50, kr50 = skr_from_rates(r50, mu1=MU1, mu2=MU2, p_mu1=P1, p_Z=PZ,
                                 n_Z_block=1e9, rep_rate=REP)
    assert kr25.feasible and skr25 > 0
    assert skr25 > skr50 > 0          # nearer link -> higher rate


def test_finite_size_penalty(rates25):
    # Larger PA block -> higher secret fraction (smaller statistical penalty).
    fracs = []
    for nZ in (1e6, 1e7, 1e8, 1e9):
        _skr, kr = skr_from_rates(rates25, mu1=MU1, mu2=MU2, p_mu1=P1, p_Z=PZ,
                                  n_Z_block=nZ, rep_rate=REP)
        fracs.append(kr.length / kr.nZ)
    assert all(a < b + 1e-12 for a, b in zip(fracs, fracs[1:]))
    assert fracs[-1] > fracs[0]
