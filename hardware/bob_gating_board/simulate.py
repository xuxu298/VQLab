"""Run the self-differencing front-end SPICE netlist and quantify the cancellation.

Runs ngspice on sd_frontend.cir, reads the waveform dump, computes the gate-transient
suppression (raw vs self-differenced) and the avalanche visibility, and writes a figure to
demos/figures/h1_sd_cancellation.png.

Run:  python -m hardware.bob_gating_board.simulate   (from the repo root)
      python simulate.py                              (from this directory)
"""
from __future__ import annotations

import os
import subprocess

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CIR = os.path.join(HERE, "sd_frontend.cir")
DATA = os.path.join(HERE, "sd_frontend.data")
FIGDIR = os.path.join(HERE, "..", "..", "demos", "figures")
TAV = 4.0e-9  # avalanche time (matches the netlist .param tav)


def run_ngspice() -> None:
    # ngspice -b can return a nonzero code even on success, so verify by output file
    subprocess.run(["ngspice", "-b", CIR], cwd=HERE, capture_output=True, text=True)
    if not os.path.exists(DATA):
        raise RuntimeError("ngspice produced no data file; is ngspice installed?")


def load() -> dict[str, np.ndarray]:
    raw = np.loadtxt(DATA, skiprows=1)
    return {"t": raw[:, 0], "det": raw[:, 1], "vsd": raw[:, 2], "gate": raw[:, 3]}


def main() -> None:
    run_ngspice()
    d = load()
    t, det, vsd = d["t"], d["det"], d["vsd"]

    # quantify away from the avalanche (steady-state periodic transient region)
    far = (t > 5.5e-9) & (t < 7.5e-9)
    raw_transient = np.max(np.abs(det[far]))
    sd_residual = np.max(np.abs(vsd[far]))
    suppression_db = 20 * np.log10(raw_transient / sd_residual)

    # avalanche peak in the SD output (near tav)
    win = (t > TAV - 0.1e-9) & (t < TAV + 0.25e-9)
    avalanche_sd = np.max(np.abs(vsd[win]))

    print("Self-differencing gate-transient cancellation")
    print(f"  raw gate transient (buries avalanche) : {raw_transient*1e3:8.2f} mV")
    print(f"  SD residual transient                 : {sd_residual*1e3:8.2f} mV")
    print(f"  => gate-transient suppression         : {suppression_db:8.1f} dB")
    print(f"  avalanche peak after SD               : {avalanche_sd*1e3:8.2f} mV")
    print(f"  avalanche-to-residual ratio (raw)     : {avalanche_sd/raw_transient:8.3f}")
    print(f"  avalanche-to-residual ratio (after SD): {avalanche_sd/sd_residual:8.2f}  "
          f"(>1 => avalanche is now discriminable)")

    tn = t * 1e9
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True)
    ax1.plot(tn, det * 1e3, color="#c0392b", lw=1.1)
    ax1.axvline(TAV * 1e9, ls=":", color="gray", alpha=0.7)
    ax1.text(TAV * 1e9 + 0.05, 0.7 * raw_transient * 1e3, "photon\navalanche",
             fontsize=8, color="gray")
    ax1.set_ylabel("raw detector v(det) (mV)")
    ax1.set_title("Bob SPAD front-end: the GHz gate transient buries the single-photon "
                  "avalanche\n(self-differencing then cancels the transient)")
    ax1.grid(alpha=0.25)

    ax2.plot(tn, vsd * 1e3, color="#27ae60", lw=1.1)
    ax2.axvline(TAV * 1e9, ls=":", color="gray", alpha=0.7)
    # zoom to the post-priming region so the avalanche vs residual is legible
    ylim = 1.6 * avalanche_sd * 1e3
    ax2.set_ylim(-ylim, ylim)
    ax2.axhline(sd_residual * 1e3, ls="--", color="#7f8c8d", alpha=0.7, lw=0.8)
    ax2.axhline(-sd_residual * 1e3, ls="--", color="#7f8c8d", alpha=0.7, lw=0.8,
                label=f"residual transient ±{sd_residual*1e3:.0f} mV")
    ax2.text(TAV * 1e9 + 0.08, 0.55 * avalanche_sd * 1e3, "avalanche\nsurvives",
             fontsize=8, color="#1e8449")
    ax2.text((TAV + 1 / 1.25e9) * 1e9 + 0.05, -0.75 * avalanche_sd * 1e3,
             "ghost\n(FPGA veto)", fontsize=7, color="gray")
    ax2.text(0.1, 0.78 * ylim, "first-cycle priming transient off-scale\n"
             "(intrinsic 1-gate SD dead time)", fontsize=7, color="#b03a2e")
    ax2.set_ylabel("self-differenced v(sd) (mV)")
    ax2.set_xlabel("time (ns)")
    ax2.set_title(f"after self-differencing: gate transient suppressed "
                  f"{suppression_db:.0f} dB; avalanche/residual = {avalanche_sd/sd_residual:.1f}")
    ax2.legend(loc="lower right", fontsize=7)
    ax2.grid(alpha=0.25)

    fig.tight_layout()
    os.makedirs(FIGDIR, exist_ok=True)
    out = os.path.abspath(os.path.join(FIGDIR, "h1_sd_cancellation.png"))
    fig.savefig(out, dpi=130)
    print(f"\n[H1] wrote {out}")


if __name__ == "__main__":
    main()
