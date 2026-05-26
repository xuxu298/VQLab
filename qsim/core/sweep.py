"""Parameter sweep & optimize — the kernel's "tuning loop" UX (spec §9).

Domain-agnostic: you give a `run_fn(**params) -> dict[str, float]` (build a device, run it,
return metrics) and either a grid of parameter values to sweep or bounds to optimize over.
This is the engine behind "vary a knob, watch the metric surface" — what a researcher does
on a real bench, made virtual.

Nothing here knows about QKD; the QKD demos just pass a run_fn that builds the decoy slice.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np


@dataclass
class SweepResult:
    """Tidy result of a sweep: the parameter combinations and the metric arrays."""

    param_names: list[str]
    combos: list[dict]                       # one dict of params per evaluated point
    metrics: dict[str, np.ndarray]           # metric_name -> values aligned with combos

    def axis(self, name: str) -> np.ndarray:
        """The values of a swept parameter, aligned with each evaluated point."""
        return np.array([c[name] for c in self.combos])

    def surface(self, x: str, y: str, metric: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Reshape a 2-parameter sweep into (X, Y, Z) grids for contour/surface plots."""
        xs = sorted({c[x] for c in self.combos})
        ys = sorted({c[y] for c in self.combos})
        Z = np.full((len(ys), len(xs)), np.nan)
        idx = {(c[x], c[y]): m for c, m in zip(self.combos, self.metrics[metric])}
        for j, yv in enumerate(ys):
            for i, xv in enumerate(xs):
                Z[j, i] = idx.get((xv, yv), np.nan)
        X, Y = np.meshgrid(np.array(xs), np.array(ys))
        return X, Y, Z

    def best(self, metric: str, maximize: bool = True) -> tuple[dict, float]:
        """The parameter combo giving the best metric value."""
        vals = self.metrics[metric]
        i = int(np.nanargmax(vals) if maximize else np.nanargmin(vals))
        return self.combos[i], float(vals[i])


def sweep(run_fn, grid: dict[str, list], *, fixed: dict | None = None) -> SweepResult:
    """Evaluate `run_fn` over the Cartesian product of `grid` (plus any `fixed` params).

    `run_fn(**params)` must return a dict of scalar metrics. Example:
        sweep(run, {"mu1": [0.3, 0.5, 0.7], "length_km": [25, 50]})
    """
    fixed = fixed or {}
    names = list(grid.keys())
    combos: list[dict] = []
    metric_lists: dict[str, list[float]] = {}
    for values in itertools.product(*(grid[n] for n in names)):
        params = dict(zip(names, values))
        out = run_fn(**{**fixed, **params})
        combos.append(params)
        for k, v in out.items():
            metric_lists.setdefault(k, []).append(float(v))
    metrics = {k: np.array(v) for k, v in metric_lists.items()}
    return SweepResult(param_names=names, combos=combos, metrics=metrics)


@dataclass
class OptimizeResult:
    best_params: dict
    best_value: float
    n_evals: int
    history: list[tuple[dict, float]] = field(default_factory=list)


def optimize(
    run_fn,
    bounds: dict[str, tuple[float, float]],
    metric: str,
    *,
    maximize: bool = True,
    fixed: dict | None = None,
    n_restarts: int = 8,
    seed: int = 0,
) -> OptimizeResult:
    """Maximize (or minimize) `metric` over `bounds` using multi-start Nelder-Mead.

    Kept dependency-light (SciPy is optional elsewhere but used here for the simplex). Good
    for the handful of continuous knobs a device-tuning problem has."""
    from scipy.optimize import minimize  # local import keeps core import-light

    fixed = fixed or {}
    names = list(bounds.keys())
    lo = np.array([bounds[n][0] for n in names])
    hi = np.array([bounds[n][1] for n in names])
    rng = np.random.default_rng(seed)
    history: list[tuple[dict, float]] = []
    sign = -1.0 if maximize else 1.0

    def objective(x):
        x = np.clip(x, lo, hi)
        params = dict(zip(names, x))
        val = float(run_fn(**{**fixed, **params})[metric])
        history.append((params, val))
        return sign * val

    starts = [lo + 0.5 * (hi - lo)]
    for _ in range(n_restarts - 1):
        starts.append(lo + rng.random(len(names)) * (hi - lo))

    best = None
    for x0 in starts:
        res = minimize(objective, x0, method="Nelder-Mead",
                       options={"xatol": 1e-3, "fatol": 1e-3, "maxiter": 400})
        if best is None or res.fun < best.fun:
            best = res

    bp = dict(zip(names, np.clip(best.x, lo, hi)))
    return OptimizeResult(best_params=bp, best_value=sign * best.fun,
                          n_evals=len(history), history=history)
