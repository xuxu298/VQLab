"""M3 milestone: an optically-pumped atomic magnetometer running on the SAME kernel as QKD.

This is the generality proof. The device (AmbientField -> AtomicVaporCell -> ProbeReadout)
reuses the kernel graph, the multi-rate scheduler and the PhaseDriftOU slow-drift impairment
unchanged, while introducing a new Bloch backend, the ENVIRONMENTAL signal type (which QKD
never used) and a new payload. Two panels:

  (A) averaging-down: the field uncertainty falls as 1/sqrt(t) toward the spin-projection-
      noise limit dB = 1/(gamma*sqrt(N*T2*t)) (Budker & Romalis, Nature Physics 2007);
  (B) sensitivity vs atom number, swept with the SAME domain-agnostic sweep harness the QKD
      tuning loop used — slope -1/2, sitting an O(1) (~e) prefactor above the quantum floor.

Run:  python -m demos.m3_magnetometer
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.core.sweep import sweep  # noqa: E402
from qsim.sensing.metrics import projection_limit_asd  # noqa: E402
from qsim.sensing.reference import load_default_profile, run_magnetometer  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)


def main() -> None:
    p = load_default_profile()
    gamma, N, T2, tau = p.value("gamma"), p.value("N_atoms"), p.value("T2"), p.value("tau")

    print("M3: Rb-87 vapor-cell magnetometer on the kernel (projection-noise-limited)")
    base = run_magnetometer(n_ticks=200, cycles_per_tick=4000, seed=0)
    print(f"  recovered field   : {base['field_estimate']*1e9:.4f} nT  (true 1.0000 nT)")
    print(f"  sensitivity (ASD) : {base['sensitivity_asd']*1e15:.3f} fT/sqrtHz")
    print(f"  projection limit  : {base['projection_limit_asd']*1e15:.3f} fT/sqrtHz")
    print(f"  ASD / limit       : {base['asd_over_limit']:.3f}  (analytic e={np.e:.3f} at tau=T2)")

    # --- Panel A: averaging down toward the projection-noise limit -------
    n_ticks_list = [10, 25, 60, 150, 400, 1000]
    emp_t, emp_dB = [], []
    for nt in n_ticks_list:
        r = run_magnetometer(n_ticks=nt, cycles_per_tick=4000, seed=7)
        emp_t.append(r["t_total"])
        emp_dB.append(r["sensitivity_at_t"])
    emp_t, emp_dB = np.array(emp_t), np.array(emp_dB)
    t_line = np.logspace(np.log10(emp_t.min()), np.log10(emp_t.max()), 100)
    dB_limit = 1.0 / (gamma * np.sqrt(N * T2 * t_line))

    # --- Panel B: sensitivity vs atom number (sweep harness reuse) -------
    Ns = [1e10, 1e11, 1e12, 1e13, 1e14]
    res = sweep(lambda **kw: run_magnetometer(n_ticks=120, cycles_per_tick=4000, seed=3, **kw),
                {"N_atoms": Ns})
    asd_dev = res.metrics["sensitivity_asd"]
    asd_lim = np.array([projection_limit_asd(N=n, T2=T2, gamma=gamma) for n in Ns])

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 5))

    axA.loglog(emp_t, emp_dB * 1e15, "o", ms=6, color="#c0392b", label="simulated device")
    axA.loglog(t_line, dB_limit * 1e15, "k--", lw=1.4,
               label=r"projection limit $1/(\gamma\sqrt{N T_2 t})$")
    axA.set_xlabel("total integration time $t$ (s)")
    axA.set_ylabel(r"field uncertainty $\delta B$ (fT)")
    axA.set_title("(A) averaging down ~ $1/\\sqrt{t}$ toward the quantum floor")
    axA.legend(loc="upper right", fontsize=8)
    axA.grid(alpha=0.25, which="both")

    axB.loglog(Ns, asd_dev * 1e15, "o-", ms=6, color="#2471a3", label="simulated device")
    axB.loglog(Ns, asd_lim * 1e15, "k--", lw=1.4, label="projection-noise limit")
    axB.set_xlabel("atom number $N$")
    axB.set_ylabel(r"sensitivity ASD (fT/$\sqrt{\mathrm{Hz}}$)")
    axB.set_title("(B) sensitivity vs $N$ (swept via the shared harness), slope $-1/2$")
    axB.legend(loc="upper right", fontsize=8)
    axB.grid(alpha=0.25, which="both")

    fig.suptitle("M3: atomic magnetometer on the qsim kernel — kernel generality proof",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(FIGDIR, "m3_magnetometer.png")
    fig.savefig(out, dpi=130)
    print(f"\n[M3] wrote {out}")


if __name__ == "__main__":
    main()
