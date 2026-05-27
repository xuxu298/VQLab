"""C1/C2/C3 demo: the multi-domain reference-design configurator.

Prints the unified configuration report for all four domains (QKD link, atomic magnetometer,
qubit processor, quantum RNG) from one `configure(domain, knobs)` core, then shows the QKD
detector trade-off (SKR vs distance + whole-link BOM cost split). The GUI (gui/) drives this
same core.

Run:  python -m demos.c1_configurator
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.configurator import configure  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)


def main() -> None:
    print("Multi-domain configurator — one configure(domain, knobs) core:\n")
    for dom, knobs in [
        ("qkd", {"detector": "ingaas_sd", "distance_km": 25}),
        ("sensing", {"atom_number": 1e12, "T2_ms": 5, "tau_ms": 5}),
        ("qchw", {"n_qubits": 2, "T1_us": 50, "T2_us": 70, "t_gate_ns": 40}),
        ("qrng", {"mu": 0.5, "eta_a": 0.30, "eta_b": 0.15}),
    ]:
        print(configure(dom, knobs).format())
        print()

    # QKD detector trade-off: SKR vs distance + whole-link BOM cost split
    dists = np.linspace(1, 150, 40)
    curves, split = {}, {}
    for key, label, col in [("ingaas_sd", "InGaAs SD", "#2471a3"),
                            ("snspd", "SNSPD", "#c0392b")]:
        skr = [configure("qkd", {"detector": key, "distance_km": float(d)}).m("skr_bps")
               for d in dists]
        curves[label] = (np.array([s if s > 0 else np.nan for s in skr]), col)
        split[label] = configure("qkd", {"detector": key, "distance_km": 25}).cost_by_side

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [2, 1]})
    for label, (skr, col) in curves.items():
        m = np.isfinite(skr)
        axA.semilogy(dists[m], skr[m], "-", color=col, lw=2, label=label)
    axA.set_xlabel("metro distance (km)")
    axA.set_ylabel("secret-key rate (bps, log)")
    axA.set_title("(A) QKD: one knob (detector) → sim updates")
    axA.legend(loc="upper right")
    axA.grid(alpha=0.25, which="both")

    labels = list(split.keys())
    sides = ["Alice", "shared", "Bob"]
    side_cols = {"Alice": "#7fb3d5", "shared": "#aab7b8", "Bob": "#e59866"}
    bottom = np.zeros(len(labels))
    for sd in sides:
        vals = np.array([split[l].get(sd, 0) / 1e3 for l in labels])
        axB.bar(labels, vals, bottom=bottom, label=sd, color=side_cols[sd])
        bottom += vals
    for i in range(len(labels)):
        axB.text(i, bottom[i], f"${bottom[i]:,.0f}k", ha="center", va="bottom", fontsize=9)
    axB.set_ylabel("whole-link BOM cost (k USD)")
    axB.set_title("(B) …and the BOM updates too")
    axB.legend(loc="upper left", fontsize=8)
    axB.grid(alpha=0.25, axis="y")

    fig.suptitle("C3: multi-domain configurator (QKD / sensing / QC) — one DeviceSpec core",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(FIGDIR, "c1_configurator.png")
    fig.savefig(out, dpi=130)
    print(f"[C3] wrote {out}")


if __name__ == "__main__":
    main()
