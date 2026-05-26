"""C1 demo: the reference-design configurator — turn knobs, see sim + BOM update together.

Loads two DeviceSpecs (InGaAs self-differencing vs SNSPD), prints their unified configuration
reports, and sweeps the distance knob to show the performance/cost trade-off the configurator
exposes: SKR vs distance for both detector variants + their BOM cost. Same call drives the
qsim behavioural sim and the hardware build.

Run:  python -m demos.c1_configurator
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.configurator import DeviceSpec, configure  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)


def main() -> None:
    ingaas = DeviceSpec(name="qkd_metro_ingaas", detector="ingaas_sd", distance_km=25.0)
    snspd = ingaas.replace(name="qkd_metro_snspd", detector="snspd", distance_km=50.0)

    for spec in (ingaas, snspd):
        print(configure(spec).format())
        print()

    # sweep the distance knob for both variants
    dists = np.linspace(1, 150, 40)
    curves = {}
    split = {}
    for key, label, col in [("ingaas_sd", "InGaAs SD", "#2471a3"),
                            ("snspd", "SNSPD", "#c0392b")]:
        skr = []
        for d in dists:
            rep = configure(ingaas.replace(detector=key, distance_km=float(d)))
            skr.append(rep.skr_bps if rep.feasible else np.nan)
        curves[label] = (np.array(skr), col)
        split[label] = configure(ingaas.replace(detector=key)).cost_by_side

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [2, 1]})
    for label, (skr, col) in curves.items():
        m = np.isfinite(skr) & (skr > 0)
        axA.semilogy(dists[m], skr[m], "-", color=col, lw=2, label=label)
    axA.set_xlabel("metro distance (km)")
    axA.set_ylabel("secret-key rate (bps, log)")
    axA.set_title("(A) one knob (detector) → sim updates: SKR vs distance")
    axA.legend(loc="upper right")
    axA.grid(alpha=0.25, which="both")

    # (B) whole-link BOM cost, stacked by side (Alice / shared / Bob)
    labels = list(split.keys())
    sides = ["Alice", "shared", "Bob"]
    side_cols = {"Alice": "#7fb3d5", "shared": "#aab7b8", "Bob": "#e59866"}
    bottom = np.zeros(len(labels))
    for sd in sides:
        vals = np.array([split[l][sd] / 1e3 for l in labels])
        axB.bar(labels, vals, bottom=bottom, label=sd, color=side_cols[sd])
        bottom += vals
    for i, l in enumerate(labels):
        axB.text(i, bottom[i], f"${bottom[i]:,.0f}k", ha="center", va="bottom", fontsize=9)
    axB.set_ylabel("whole-link BOM cost (k USD)")
    axB.set_title("(B) …and the full Alice+Bob BOM updates too")
    axB.legend(loc="upper left", fontsize=8)
    axB.grid(alpha=0.25, axis="y")

    fig.suptitle("C2: reference-design configurator — one DeviceSpec drives the behavioural "
                 "sim AND the whole-link BOM", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(FIGDIR, "c1_configurator.png")
    fig.savefig(out, dpi=130)
    print(f"[C1] wrote {out}")


if __name__ == "__main__":
    main()
