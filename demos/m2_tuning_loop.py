"""M2 demo: the tuning loop — sweep a knob, watch the secret-key-rate surface, optimize.

This is the product's core UX made concrete on the QKD reference design: vary the source
intensity (and basis bias) and see how the *proven* finite-key SKR responds, then let the
optimizer find the best operating point — exactly what a researcher does on a real bench,
but virtual and free. The harness (qsim/core/sweep.py) is domain-agnostic; here it drives
the 1-decoy finite-key model.

Run:  python -m demos.m2_tuning_loop
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.core.sweep import optimize, sweep  # noqa: E402
from qsim.qkd.channel import ChannelParams  # noqa: E402
from qsim.qkd.keyrate import skr_for_params  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)

PARAMS = ChannelParams(eta_det=0.5, p_dc=5e-9, e_d=0.01)
LOSS_DB = 30.0
N_Z = 1e9
REP = 1e9


def run(mu1, p_Z, *, mu2=0.1, p_mu1=0.7):
    skr, _ = skr_for_params(LOSS_DB, N_Z, mu1, mu2, p_mu1, p_Z, rep_rate=REP,
                            params=PARAMS, eps_sec=1e-9, eps_cor=1e-15, f_ec=1.16)
    return {"skr": skr}


def main() -> None:
    print(f"Tuning loop on the decoy-BB84 finite-key model (loss={LOSS_DB} dB, n_Z={N_Z:.0e})\n")

    # 1) 1-D sweep: SKR vs signal intensity mu1 (the classic 'optimal mu' tuning task)
    mu1_grid = list(np.round(np.linspace(0.15, 0.9, 31), 4))
    s1 = sweep(run, {"mu1": mu1_grid}, fixed={"p_Z": 0.9})
    best_mu, best_skr = s1.best("skr")
    print(f"  1-D sweep over mu1 @ p_Z=0.9:  optimal mu1 = {best_mu['mu1']:.3f}  "
          f"-> SKR = {best_skr:.3e} Hz")

    # 2) 2-D sweep: SKR surface over (mu1, p_Z)
    s2 = sweep(run, {"mu1": list(np.round(np.linspace(0.15, 0.9, 25), 4)),
                     "p_Z": list(np.round(np.linspace(0.5, 0.97, 25), 4))})
    bc, bv = s2.best("skr")
    print(f"  2-D sweep over (mu1, p_Z):     optimum mu1={bc['mu1']:.3f}, p_Z={bc['p_Z']:.3f} "
          f"-> SKR = {bv:.3e} Hz")

    # 3) continuous optimize (Nelder-Mead) — should match the grid optimum
    opt = optimize(run, {"mu1": (0.15, 0.9), "p_Z": (0.5, 0.97)}, "skr",
                   maximize=True, n_restarts=6, seed=1)
    print(f"  optimizer ({opt.n_evals} evals):        mu1={opt.best_params['mu1']:.3f}, "
          f"p_Z={opt.best_params['p_Z']:.3f} -> SKR = {opt.best_value:.3e} Hz")

    # --- figure -----------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    mu = s1.axis("mu1")
    ax1.plot(mu, s1.metrics["skr"], "-", color="#2471a3")
    ax1.plot(best_mu["mu1"], best_skr, "o", color="#c0392b", ms=8,
             label=f"optimum mu1={best_mu['mu1']:.2f}")
    ax1.set_xlabel("signal intensity $\\mu_1$ (photons/pulse)")
    ax1.set_ylabel("secret-key rate (Hz)")
    ax1.set_title(f"Tuning $\\mu_1$ @ {LOSS_DB:.0f} dB, $p_Z$=0.9")
    ax1.legend()
    ax1.grid(alpha=0.25)

    X, Y, Z = s2.surface("mu1", "p_Z", "skr")
    cs = ax2.contourf(X, Y, np.where(Z > 0, Z, np.nan), levels=20, cmap="viridis")
    ax2.plot(opt.best_params["mu1"], opt.best_params["p_Z"], "*", color="#e74c3c", ms=16,
             label="optimizer")
    fig.colorbar(cs, ax=ax2, label="SKR (Hz)")
    ax2.set_xlabel("signal intensity $\\mu_1$")
    ax2.set_ylabel("basis bias $p_Z$")
    ax2.set_title("SKR surface — the sensitivity map you 'feel' before touching hardware")
    ax2.legend(loc="lower left")

    fig.tight_layout()
    p = os.path.join(FIGDIR, "m2_tuning_loop.png")
    fig.savefig(p, dpi=130)
    print(f"\n[M2] wrote {p}")


if __name__ == "__main__":
    main()
