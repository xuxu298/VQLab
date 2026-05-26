"""Tests for the QRNG plugin — proof the kernel hosts a second domain (spec §10, M2).

The QRNG reuses the kernel graph/scheduler, FockBackend, and DarkCount with no new kernel
code; these tests check its randomness metrics respond correctly to device imperfections.
"""
from qsim.qrng.metrics import min_entropy
from qsim.qrng.reference import run_qrng


def test_balanced_qrng_is_near_ideal():
    r = run_qrng(eta_a=0.20, eta_b=0.20, seed=1)
    assert r["bias"] < 0.01
    assert r["min_entropy"] > 0.99
    assert 0.0 < r["sift_efficiency"] < 1.0
    assert r["n0"] > 0 and r["n1"] > 0


def test_efficiency_mismatch_biases_and_lowers_entropy():
    bal = run_qrng(eta_a=0.20, eta_b=0.20, seed=1)
    mis = run_qrng(eta_a=0.25, eta_b=0.15, seed=1)
    assert mis["bias"] > 0.05
    assert mis["min_entropy"] < bal["min_entropy"]
    assert mis["min_entropy"] < 0.9


def test_min_entropy_bounded_and_monotonic_in_mismatch():
    # Larger detector imbalance -> lower extractable min-entropy.
    hs = [run_qrng(eta_a=0.20 + d, eta_b=0.20 - d, seed=2)["min_entropy"]
          for d in (0.0, 0.02, 0.05, 0.08)]
    assert all(h <= 1.0 + 1e-9 for h in hs)
    assert all(a >= b - 1e-9 for a, b in zip(hs, hs[1:]))   # non-increasing


def test_min_entropy_formula_limits():
    assert min_entropy(100, 100) == 1.0          # perfectly balanced -> 1 bit
    assert min_entropy(100, 0) == 0.0            # fully biased -> 0 bits
