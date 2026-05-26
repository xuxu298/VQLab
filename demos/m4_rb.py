"""M4 credibility step: Randomized Benchmarking recovers the gate error.

RB [Magesan et al., PRL 106, 180504 (2011)] is how real QC-hardware groups report gate
quality. We run length-m random-Clifford sequences on a noisy qubit, fit the survival decay
F(m) = A p^m + B, and read off the error-per-Clifford r = (1-p)/2. The validation: r matches
the INDEPENDENTLY-computed average gate infidelity of the injected T1/T2 channel (an exact
Pauli-transfer-matrix quantity) — a non-circular check of the whole gate+noise+fit stack.

Run:  python -m demos.m4_rb
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.qchw.backend import DensityMatrixBackend  # noqa: E402
from qsim.qchw.rb import run_rb  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)

CONFIGS = [
    # (label, T1, T2, t_gate, color)
    ("good:  T1=100us T2=120us tg=20ns", 100e-6, 120e-6, 20e-9, "#27ae60"),
    ("typ.:  T1=50us  T2=40us  tg=30ns", 50e-6, 40e-6, 30e-9, "#2471a3"),
    ("noisy: T1=30us  T2=55us  tg=40ns", 30e-6, 55e-6, 40e-9, "#c0392b"),
]


def main() -> None:
    print("M4: randomized benchmarking — EPC vs analytic channel infidelity")
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for label, T1, T2, tg, col in CONFIGS:
        be = DensityMatrixBackend(1, T1=T1, T2=T2)
        r_an = be.avg_gate_infidelity(be.relax_channel_matrix(tg))
        m_max = int(0.7 / r_an)
        lengths = np.unique(np.linspace(1, m_max, 9).astype(int))
        res = run_rb(T1=T1, T2=T2, t_gate=tg, lengths=lengths, n_seq=120, seed=2)
        print(f"  {label}:  RB EPC={res.epc:.3e}  analytic={r_an:.3e}  "
              f"ratio={res.epc / r_an:.3f}")

        mm = np.linspace(lengths.min(), lengths.max(), 200)
        ax.plot(res.lengths, res.survival, "o", color=col, ms=5)
        ax.plot(mm, res.A * res.p ** mm + res.B, "-", color=col, lw=1.5,
                label=f"{label}\n  EPC={res.epc:.2e} (analytic {r_an:.2e})")

    ax.set_xlabel("sequence length $m$ (number of Cliffords)")
    ax.set_ylabel("survival probability $P(0)$")
    ax.set_title("M4 validation: RB decay $F(m)=A p^m+B$ — fitted EPC matches the\n"
                 "analytic T1/T2 channel infidelity (non-circular check)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    out = os.path.join(FIGDIR, "m4_rb.png")
    fig.savefig(out, dpi=130)
    print(f"\n[M4] wrote {out}")


if __name__ == "__main__":
    main()
