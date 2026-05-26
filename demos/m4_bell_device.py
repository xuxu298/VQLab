"""M4 milestone: a noisy 2-qubit Bell generator running on the SAME kernel as QKD/sensing.

The genuinely-new capability M3 could not show: a multi-qubit density matrix and an entangling
CNOT flowing through the unchanged graph + multi-rate scheduler. Two panels:

  (A) the slow RZ phase-miscalibration drift (reusing PhaseDriftOU) makes the Bell fidelity
      wander tick-to-tick — the QC analog of QKD's drifting-AMZI QBER time-series — while the
      computational-basis parity stays blind to the phase error (why you need tomography);
  (B) coherence-limited fidelity: relaxation over longer gates degrades the prepared Bell pair.

Run:  python -m demos.m4_bell_device
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.qchw.reference import bell_fidelity_under_noise, build_bell_device  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)


def main() -> None:
    # --- Panel A: fidelity time-series under slow calibration drift ------
    g, sched, rdo, prm = build_bell_device(miscal_sigma=6.0)
    records = sched.run(n_ticks=600, dt_slow=2e-4, pulses_per_tick=256,
                        rng=np.random.default_rng(3), record=True)
    t = np.array([r["t"] for r in records])
    fid = np.array([r.get("fidelity_tick", np.nan) for r in records])
    mean_fid, parity = rdo.stats()
    print("M4: Bell generator on the kernel with slow phase-miscalibration drift")
    print(f"  mean Bell fidelity = {mean_fid:.4f}   parity success = {parity:.4f}")
    print(f"  (fidelity tracks the drift; parity is phase-blind)")

    # --- Panel B: coherence-limited fidelity vs gate time ---------------
    T1, T2 = 50e-6, 70e-6
    tgs = np.linspace(0, 400e-9, 60)
    fids = [bell_fidelity_under_noise(T1=T1, T2=T2, t_gate=tg) for tg in tgs]

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 5))
    axA.plot(t * 1e3, fid, "-", color="#8e44ad", lw=1.2, label="Bell fidelity / tick")
    axA.axhline(mean_fid, ls="--", color="gray", alpha=0.7, label=f"mean = {mean_fid:.3f}")
    axA.axhline(parity, ls=":", color="#16a085", alpha=0.9,
                label=f"parity P(00)+P(11) = {parity:.3f} (phase-blind)")
    axA.set_xlabel("time (ms)")
    axA.set_ylabel("Bell-state fidelity")
    axA.set_title("(A) fidelity wanders with slow phase drift (multi-rate)")
    axA.legend(loc="lower left", fontsize=8)
    axA.grid(alpha=0.25)

    axB.plot(tgs * 1e9, fids, "-", color="#2471a3", lw=1.8)
    axB.set_xlabel("gate duration $t_{gate}$ (ns)")
    axB.set_ylabel("Bell-state fidelity")
    axB.set_title(f"(B) coherence-limited fidelity (T1={T1*1e6:.0f}us, T2={T2*1e6:.0f}us)")
    axB.grid(alpha=0.25)

    fig.suptitle("M4: 2-qubit Bell generator on the qsim kernel — multi-qubit + entanglement",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(FIGDIR, "m4_bell_device.png")
    fig.savefig(out, dpi=130)
    print(f"\n[M4] wrote {out}")


if __name__ == "__main__":
    main()
