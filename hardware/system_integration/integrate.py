"""System integration: tie Alice (H3) + fiber + Bob (H1/H2) + finite-key into ONE link story.

Two independent reach limits, each from a different subsystem, only visible once assembled:
  * LOSS-limited reach  — the finite-key bound (configurator) runs out of secret key as fiber
    attenuation grows;
  * TIMING-limited reach — the end-to-end timing budget (timing_budget.py) hits the gate-window
    rule as chromatic dispersion grows.

This script sweeps distance, gets the loss-limited SKR/QBER from the *validated* configurator and
the timing budget from the integration layer, prints a per-span table + the Phase-1 (25 km)
loop-closed summary (same idiom as H1/H3), and renders the end-to-end figure.

Run:  python -m hardware.system_integration.integrate            (writes the figure)
      python -m hardware.system_integration.integrate --no-plot  (text only)
"""
from __future__ import annotations

import sys

from qsim.configurator import configure
from qsim.configurator.catalog import DETECTORS, SOURCES

from .timing_budget import (BUDGET_FRACTION, build_budget, dispersion_limited_reach_km,
                            timing_efficiency)

GATE_GHZ = 1.25
SOURCE_KEY = "gainswitched_dfb"
DET_KEY = "ingaas_sd"
PHASE1_KM = 25.0


def _link(distance_km: float):
    """One span: loss-limited SKR/QBER from the configurator + the end-to-end timing budget."""
    rep = configure("qkd", {"source": SOURCE_KEY, "detector": DET_KEY,
                            "gate_rate_ghz": GATE_GHZ, "distance_km": distance_km})
    budget = build_budget(distance_km, GATE_GHZ * 1e9,
                          source_jitter_ps=SOURCES[SOURCE_KEY].jitter_ps,
                          detector_jitter_ps=DETECTORS[DET_KEY].jitter_ps)
    return rep, budget


def analyze(distances: list[float] | None = None) -> dict:
    distances = distances or [10, 25, 50, 75, 100]
    rows = []
    for L in distances:
        rep, b = _link(L)
        rows.append({
            "km": L, "loss_db": rep.m("loss_db"), "qber": rep.m("qber"),
            "skr": rep.m("skr_bps"), "jitter_ps": b.total_ps, "budget_ps": b.budget_ps,
            "margin": b.margin, "eta_timing": timing_efficiency(b.total_ps, b.gate_period_ps),
        })
    fixed = build_budget(PHASE1_KM, GATE_GHZ * 1e9, SOURCES[SOURCE_KEY].jitter_ps,
                         DETECTORS[DET_KEY].jitter_ps).fixed_ps
    reach_timing = dispersion_limited_reach_km(GATE_GHZ * 1e9, fixed)
    return {"rows": rows, "fixed_ps": fixed, "timing_reach_km": reach_timing}


def main(argv: list[str]) -> int:
    do_plot = "--no-plot" not in argv
    a = analyze([10, 25, 50, 75, 100])
    rep1, b1 = _link(PHASE1_KM)

    print("QKD link — end-to-end integration (Alice H3 + fiber + Bob H1/H2 + finite-key)")
    print(f"  config: {SOURCES[SOURCE_KEY].label}, {DETECTORS[DET_KEY].label}, {GATE_GHZ} GHz")
    print(f"  gate period {b1.gate_period_ps:.0f} ps   timing budget (25%) {b1.budget_ps:.0f} ps\n")

    print(f"  {'span':>6} {'loss':>7} {'QBER':>7} {'SKR':>11} {'jitter':>9} {'margin':>8} {'η_time':>8}")
    for r in a["rows"]:
        skr = (f"{r['skr']/1e6:.2f} Mbps" if r["skr"] >= 1e5 else
               (f"{r['skr']/1e3:.1f} kbps" if r["skr"] >= 1e3 else f"{r['skr']:.0f} bps"))
        print(f"  {r['km']:>4.0f}km {r['loss_db']:>6.1f}dB {r['qber']:>6.2f}% {skr:>11} "
              f"{r['jitter_ps']:>7.0f}ps {r['margin']:>7.2f}x {r['eta_timing']*100:>6.2f}%")

    print(f"\n  Two independent reach limits:")
    print(f"    timing-limited (dispersion -> 25% gate rule) : ~{a['timing_reach_km']:.0f} km")
    print(f"    loss-limited   (finite-key key -> 0)         : InGaAs ~60-80 km (SNSPD further)")

    # Phase-1 loop-closure check (same idiom as H1/H3)
    ok = (rep1.feasible and b1.within_budget and rep1.m("skr_bps") > 0
          and PHASE1_KM < a["timing_reach_km"])
    print(f"\n  Phase-1 @ {PHASE1_KM:.0f} km:")
    print(f"    timing {b1.total_ps:.0f} ps / budget {b1.budget_ps:.0f} ps = {b1.margin:.2f}x "
          f"(η_timing {timing_efficiency(b1.total_ps, b1.gate_period_ps)*100:.3f}%)")
    print(f"    QBER {rep1.m('qber'):.2f} %   SKR {rep1.m('skr_bps')/1e6:.2f} Mbps   "
          f"feasible={rep1.feasible}")
    print(f"    -> dominated by the LOSS limit, with ~{a['timing_reach_km']/PHASE1_KM:.1f}x timing headroom")
    print(f"\n  => {'INTEGRATED OK' if ok else 'MISMATCH'}: assembled link closes at Phase-1; "
          f"loss limits reach first, dispersion gives a separate (further) timing limit.")

    if do_plot:
        _plot(a, b1)
    return 0 if ok else 1


def _plot(a: dict, b1) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from .timing_budget import dispersion_ps

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))
    fig.suptitle("QKD link — end-to-end integration: one timing budget, two reach limits",
                 fontsize=13, fontweight="bold")

    # --- left: timing-budget bar chart at Phase-1 (25 km) ---
    short = ["Alice\nsource", "Bob\ndetector", "Clock\nsync", "TDC", "Dispersion\n(fiber)"]
    names = short[:len(b1.contributions)]
    vals = [c.ps for c in b1.contributions]
    colors = ["#B8860B" if c.distance_dependent else "#2F5B94" for c in b1.contributions]
    x = np.arange(len(names))
    bars = axL.bar(x, vals, color=colors, width=0.62)
    axL.bar(len(names), b1.total_ps, color="#0A1A33", width=0.62)
    for xi, v in list(zip(x, vals)) + [(len(names), b1.total_ps)]:
        axL.text(xi, v + 3, f"{v:.0f}", ha="center", va="bottom", fontsize=8, color="#0A1A33")
    axL.axhline(b1.budget_ps, ls="--", color="#B91C1C", lw=1.6,
                label=f"budget = 25% gate period ({b1.budget_ps:.0f} ps)")
    axL.set_xticks(list(x) + [len(names)])
    axL.set_xticklabels(names + ["RSS\ntotal"], fontsize=8.5)
    axL.set_ylabel("timing spread (ps, FWHM-class)")
    axL.set_title(f"Timing budget @ {PHASE1_KM:.0f} km  (total {b1.total_ps:.0f} ps, "
                  f"{b1.margin:.2f}x budget)", fontsize=10)
    axL.legend(fontsize=8, loc="upper left")
    axL.grid(axis="y", alpha=0.3)

    # --- right: total jitter & SKR vs distance ---
    Ls = np.linspace(1, 120, 120)
    fixed = a["fixed_ps"]
    disp = np.array([dispersion_ps(L) for L in Ls])
    total = np.sqrt(fixed ** 2 + disp ** 2)
    axR.plot(Ls, total, color="#0A1A33", lw=2.2, label="total timing jitter (RSS)")
    axR.plot(Ls, disp, color="#B8860B", lw=1.6, ls="-.", label="chromatic dispersion only")
    axR.axhline(fixed, color="#2F5B94", lw=1.3, ls=":", label=f"fixed floor ({fixed:.0f} ps)")
    axR.axhline(b1.budget_ps, color="#B91C1C", lw=1.6, ls="--",
                label=f"25% gate budget ({b1.budget_ps:.0f} ps)")
    axR.axvline(a["timing_reach_km"], color="#B91C1C", lw=1.2, alpha=0.6)
    axR.annotate(f"timing-limited\nreach ~{a['timing_reach_km']:.0f} km",
                 xy=(a["timing_reach_km"], b1.budget_ps), xytext=(a["timing_reach_km"] - 47, b1.budget_ps + 60),
                 fontsize=8, color="#B91C1C",
                 arrowprops=dict(arrowstyle="->", color="#B91C1C"))
    axR.axvline(PHASE1_KM, color="#15803D", lw=1.4, alpha=0.7)
    axR.annotate("Phase-1\n25 km", xy=(PHASE1_KM, fixed), xytext=(PHASE1_KM + 3, fixed - 55),
                 fontsize=8, color="#15803D")
    axR.set_xlabel("fiber span (km)")
    axR.set_ylabel("timing jitter (ps)")
    axR.set_ylim(0, max(total) * 1.15)
    axR.set_title("Timing vs distance — dispersion sets a 2nd reach limit", fontsize=10)
    axR.grid(alpha=0.3)

    # SKR on a twin axis (loss-limited reach, from the validated configurator)
    ax2 = axR.twinx()
    Ls2 = list(range(2, 121, 3))
    skr = [max(configure("qkd", {"source": SOURCE_KEY, "detector": DET_KEY,
                                 "gate_rate_ghz": GATE_GHZ, "distance_km": L}).m("skr_bps"), 1.0)
           for L in Ls2]
    ax2.semilogy(Ls2, skr, color="#9333EA", lw=1.8, alpha=0.8, label="secret-key rate (loss-limited)")
    ax2.set_ylabel("secret-key rate (bps)", color="#9333EA")
    ax2.tick_params(axis="y", labelcolor="#9333EA")
    lines = axR.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = axR.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    axR.legend(lines, labels, fontsize=7.5, loc="upper center")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = "demos/figures/system_integration.png"
    fig.savefig(out, dpi=130)
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
