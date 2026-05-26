"""Close the design-validation loop: feed the H1 detector parameters into qsim.

The whole point of building the simulator first is that a hardware choice can be checked
against it. Here we take the measured/verified parameters of the self-differencing
InGaAs/InP detector this board implements (PDE, dark-count probability per gate, dead time)
and run qsim's *validated* 1-decoy finite-key model (the same code that reproduced Rusca
2018) to predict QBER and secret-key rate over the Phase-1 metro span — i.e. the simulator
tells us whether the detector we designed is good enough.

Run:  python -m hardware.bob_gating_board.validate_with_qsim   (from the repo root)
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.qkd.channel import ChannelParams, gain_qber  # noqa: E402
from qsim.qkd.keyrate import optimize_skr  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "demos", "figures")

# --- H1 detector parameters (web-verified, compact SD module class) ---------
#   PDE 30%, dark-count prob 8e-7/gate @ 3 ns hold-off  [arXiv:2401.02625];
#   self-differencing -> near dead-time-free [Comandar et al., arXiv:1412.1586].
ETA_DET = 0.30
P_DARK = 8e-7          # per gate, per detector
E_MISALIGN = 0.01      # 1% intrinsic optical/misalignment error (AMZI visibility ~98%)
TAU_DEAD = 3e-9        # hold-off time
REP_RATE = 1.25e9      # gating / clock rate
FIBER_ALPHA = 0.2      # dB/km, G.652 @ 1550 nm
BOB_INSERTION_DB = 3.5  # AMZI + DWDM filter + connectors (Bob optics, from BOM)
N_Z_BLOCK = 1e8        # finite-key Z-basis block size (one PA block)


def params() -> ChannelParams:
    return ChannelParams(eta_det=ETA_DET, fiber_alpha=FIBER_ALPHA, p_dc=P_DARK,
                         e_d=E_MISALIGN, tau_dead=TAU_DEAD)


def evaluate(distance_km: float) -> tuple[float, float]:
    """(QBER at the optimum, finite-key SKR in Hz) for the designed detector."""
    loss_db = FIBER_ALPHA * distance_km + BOB_INSERTION_DB
    pt = optimize_skr(loss_db, N_Z_BLOCK, rep_rate=REP_RATE, params=params(),
                      f_ec=1.16, eps_sec=1e-9, eps_cor=1e-15, n_restarts=6)
    eta = ETA_DET * 10.0 ** (-loss_db / 10.0)
    _, qber = gain_qber(pt.mu1, eta, P_DARK, E_MISALIGN)
    return qber, pt.skr


def main() -> None:
    print("H1 design validation via qsim 1-decoy finite-key model")
    print(f"  detector: PDE={ETA_DET:.0%}, p_dark={P_DARK:.0e}/gate, e_d={E_MISALIGN:.0%}, "
          f"rep={REP_RATE:.2e} Hz, Bob loss={BOB_INSERTION_DB} dB, n_Z={N_Z_BLOCK:.0e}")
    print(f"  {'dist (km)':>10} {'loss (dB)':>10} {'QBER':>8} {'SKR (bps)':>14}")
    for dkm in (10, 25, 50, 75):
        qber, skr = evaluate(dkm)
        loss = FIBER_ALPHA * dkm + BOB_INSERTION_DB
        print(f"  {dkm:>10.0f} {loss:>10.1f} {qber*100:>7.2f}% {skr:>14,.0f}")

    dists = np.linspace(1, 120, 60)
    skrs = np.array([evaluate(d)[1] for d in dists])
    q25, skr25 = evaluate(25.0)

    m = skrs > 0
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.semilogy(dists[m], skrs[m], "-", color="#2471a3", lw=1.8)
    ax.plot([25], [skr25], "o", color="#c0392b", ms=8,
            label=f"Phase-1 @ 25 km: QBER {q25*100:.1f}%, SKR {skr25/1e3:.0f} kbps")
    ax.set_xlabel("metro distance (km)   [0.2 dB/km + 3.5 dB Bob optics]")
    ax.set_ylabel("finite-key secret-key rate (bps, log)")
    ax.set_title("H1: predicted SKR of the designed self-differencing InGaAs detector\n"
                 "(qsim validated finite-key model — the sim checks the hardware choice)")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.25, which="both")
    fig.tight_layout()
    os.makedirs(FIGDIR, exist_ok=True)
    out = os.path.abspath(os.path.join(FIGDIR, "h1_designed_detector_skr.png"))
    fig.savefig(out, dpi=130)
    print(f"\n[H1] wrote {out}")


if __name__ == "__main__":
    main()
