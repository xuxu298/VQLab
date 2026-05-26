"""Tests for the kernel sweep/optimize harness (qsim/core/sweep.py).

Uses a cheap analytic objective so the tests are fast and deterministic — the harness is
domain-agnostic, so this exercises exactly what the QKD tuning demos rely on.
"""
import numpy as np

from qsim.core.sweep import optimize, sweep


def quad(x, y):
    # smooth bump peaked at (x, y) = (0.4, 0.7), value 1.0
    return {"score": 1.0 - (x - 0.4) ** 2 - (y - 0.7) ** 2, "x_plus_y": x + y}


def test_sweep_grid_shape_and_metrics():
    r = sweep(quad, {"x": [0.0, 0.4, 0.8], "y": [0.5, 0.7]})
    assert len(r.combos) == 6
    assert set(r.metrics) == {"score", "x_plus_y"}
    assert r.axis("x").shape == (6,)


def test_sweep_best_finds_peak_on_grid():
    r = sweep(quad, {"x": [0.0, 0.4, 0.8], "y": [0.5, 0.7]})
    combo, val = r.best("score", maximize=True)
    assert combo == {"x": 0.4, "y": 0.7}
    assert val == 1.0


def test_sweep_surface_reshapes_2d():
    r = sweep(quad, {"x": [0.0, 0.4, 0.8], "y": [0.5, 0.7]})
    X, Y, Z = r.surface("x", "y", "score")
    assert X.shape == Z.shape == (2, 3)        # (len(y), len(x))
    assert np.nanmax(Z) == 1.0


def test_optimize_recovers_continuous_optimum():
    res = optimize(quad, {"x": (0.0, 1.0), "y": (0.0, 1.0)}, "score",
                   maximize=True, n_restarts=5, seed=1)
    assert abs(res.best_params["x"] - 0.4) < 1e-2
    assert abs(res.best_params["y"] - 0.7) < 1e-2
    assert res.best_value > 0.999
    assert res.n_evals > 0


def test_optimize_can_minimize():
    res = optimize(quad, {"x": (0.0, 1.0), "y": (0.0, 1.0)}, "x_plus_y",
                   maximize=False, n_restarts=3, seed=2)
    assert res.best_value < 0.05               # minimum of x+y on [0,1]^2 is 0 at origin
