"""M0 make-or-break: the batched multi-rate engine vs a brute-force per-pulse reference.

Spec §14 names risk #1 as "multi-rate coupling — correctness & speed", mitigated by
"benchmark against a brute-force reference on a small case". These tests are that
benchmark: on a small, matched-physical-time case the cheap batched engine must reproduce
the expensive sequential reference's aggregate QBER and gain within statistical error, and
must be substantially faster.

Two regimes isolate the two distinct approximations (see qsim.qkd.validation):
  * STATIC — statistical aggregation + mean-field afterpulsing + dead-time duty.
  * DRIFT  — freezing the slow (OU phase) state per batch; driven by a SHARED trajectory so
             trajectory variance cancels and only the freezing error is tested.

We assert ABSOLUTE agreement (QBER to <0.5%, gain to <3%) rather than a pure sigma gate:
the brute-force study (demos/m0_validation) shows a small, documented ~0.1% QBER systematic
(the mean-field afterpulse over-counts because it does not see afterpulses vetoed in the
post-click dead time), so a sigma gate would tighten into that floor as samples grow. The
absolute tolerance is the physically meaningful claim and is stable across sample size. A
generous 4 sigma check is kept as a secondary guard.
"""
import pytest

from qsim.qkd.validation import compare

SECONDS = 0.02        # physical window: 2e6 reference gates @ 100 MHz, 200 batched ticks
DT_SLOW = 1e-4
QBER_ABS_TOL = 0.005  # 0.5% absolute QBER — ~5x the known mean-field-afterpulse systematic
GAIN_REL_TOL = 0.03   # 3% relative gain
SIGMA_TOL = 4.0


@pytest.fixture(scope="module")
def static_cmp():
    return compare(length_km=10.0, drift=False, seconds=SECONDS, dt_slow=DT_SLOW,
                   pulses_per_tick=20_000, seed=1)


@pytest.fixture(scope="module")
def drift_cmp():
    return compare(length_km=10.0, drift=True, seconds=SECONDS, dt_slow=DT_SLOW,
                   pulses_per_tick=20_000, seed=1)


def test_case_is_statistically_meaningful(static_cmp):
    # Enough reference clicks that the QBER CI is tight, and QBER is non-trivial (so the
    # afterpulse/optical-error physics is actually being exercised, not a degenerate ~0).
    assert static_cmp.bruteforce.sifted_clicks > 5_000
    assert static_cmp.bruteforce.qber > 0.01


def test_static_qber_matches_bruteforce(static_cmp):
    # The statistical-aggregation + mean-field-afterpulse + dead-time-duty approximation.
    assert static_cmp.dq < QBER_ABS_TOL, (
        f"QBER batched={static_cmp.batched.qber:.4f} vs bruteforce="
        f"{static_cmp.bruteforce.qber:.4f} (|Δ|={static_cmp.dq:.4f})"
    )
    assert static_cmp.qber_sigmas < SIGMA_TOL


def test_static_gain_matches_bruteforce(static_cmp):
    assert static_cmp.dgain_rel < GAIN_REL_TOL, (
        f"gain batched={static_cmp.batched.gain:.4e} vs bruteforce="
        f"{static_cmp.bruteforce.gain:.4e} (rel Δ={static_cmp.dgain_rel:.4f})"
    )
    assert static_cmp.gain_sigmas < SIGMA_TOL


def test_drift_freeze_slow_state_matches_bruteforce(drift_cmp):
    # Shared trajectory: any difference is purely the freeze-slow-state-per-batch error,
    # which should be tiny (within-batch phase wander ~0.01 rad).
    assert drift_cmp.dq < QBER_ABS_TOL, (
        f"drift QBER batched={drift_cmp.batched.qber:.4f} vs bruteforce="
        f"{drift_cmp.bruteforce.qber:.4f} (|Δ|={drift_cmp.dq:.4f})"
    )
    assert drift_cmp.qber_sigmas < SIGMA_TOL
    assert drift_cmp.dgain_rel < GAIN_REL_TOL


def test_batched_engine_is_faster(static_cmp, drift_cmp):
    # Per-pulse throughput of the vectorised batched engine vs the sequential reference.
    # (The structural win — cost independent of rep_rate — is shown in demos/m0_validation.)
    assert static_cmp.speedup > 2.0
    assert drift_cmp.speedup > 2.0
