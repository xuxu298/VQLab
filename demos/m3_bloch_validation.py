"""M3 backend-correctness step: the Bloch/Lindblad integrator vs the closed form.

The sensing plugin adds a brand-new quantum-state backend (a spin density-matrix evolver,
not photon statistics). Before trusting any sensitivity number we validate the backend the
same way M0 validated the engine: run the numeric RK4 integrator against the exact analytic
Bloch solution (Larmor precession + T2 coherence decay + T1 longitudinal recovery) and show
they coincide.

Run:  python -m demos.m3_bloch_validation
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.sensing.backend import RB87_GAMMA, SpinEnsembleBackend  # noqa: E402
from qsim.sensing.validation import validate_bloch  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)


def main() -> None:
    be = SpinEnsembleBackend(gamma=RB87_GAMMA)
    # Choose Bz so a Larmor period is ~0.1 s; T2/T1 chosen for a clearly visible decay.
    period = 0.1
    Bz = (2 * np.pi / period) / RB87_GAMMA
    T1, T2, S0 = 0.30, 0.15, 0.3
    S_start = np.array([1.0, 0.0, 0.8])
    B = np.array([0.0, 0.0, Bz])

    ts = np.linspace(0.0, 4 * period, 200)
    num = np.array([be.evolve(S_start, B, t, T1=T1, T2=T2, S0=S0,
                              n_steps=max(20, int(2000 * t / ts[-1]))) for t in ts[1:]])
    num = np.vstack([S_start, num])
    ana = np.array([be.evolve_analytic(S_start, Bz, t, T1=T1, T2=T2, S0=S0) for t in ts])

    chk = validate_bloch()
    print("M3 backend validation: numeric RK4 Bloch vs closed form")
    print(f"  max |numeric - analytic| over 5 Larmor periods = {chk.max_abs_err:.2e}")

    fig, ax = plt.subplots(figsize=(7.5, 5))
    labels = [("$S_x$", "#2471a3"), ("$S_y$", "#27ae60"), ("$S_z$", "#c0392b")]
    for i, (lab, col) in enumerate(labels):
        ax.plot(ts, ana[:, i], "-", color=col, lw=1.6, label=f"{lab} analytic")
        ax.plot(ts[::6], num[::6, i], "o", color=col, ms=4, mfc="white", mew=1.2)
    # show the T2 coherence envelope on the transverse spin
    ax.plot(ts, np.exp(-ts / T2), "k:", alpha=0.5, lw=1, label="$e^{-t/T_2}$ envelope")
    ax.plot(ts, -np.exp(-ts / T2), "k:", alpha=0.5, lw=1)

    ax.set_xlabel("time (s)")
    ax.set_ylabel("spin polarisation component")
    ax.set_title("M3 backend check: Bloch integrator (markers) vs closed form (lines)\n"
                 f"Larmor precession + $T_2$ decay + $T_1$ recovery — max err {chk.max_abs_err:.1e}")
    ax.legend(loc="upper right", ncol=2, fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    out = os.path.join(FIGDIR, "m3_bloch_validation.png")
    fig.savefig(out, dpi=130)
    print(f"\n[M3] wrote {out}")


if __name__ == "__main__":
    main()
