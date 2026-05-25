"""M0 demo — prove the kernel runs and produces sensible QKD physics.

Outputs two figures into demos/figures/:
  1. qber_skr_vs_distance.png  — classic QBER & secret-key-rate vs fiber length.
  2. qber_timeseries.png       — instantaneous QBER over time with the AMZI phase
                                 drift, comparing phase-lock OFF vs ON (this exercises
                                 the multi-rate engine: slow drift modulating fast batches).

Run:  python -m demos.m0_qber_demo      (from the repo root)
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.qkd.reference import build_bb84_slice, load_default_profile  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)


def sweep_distance(distances_km, *, pulses_per_tick=150_000, n_ticks=20, seed=1):
    qber, skr, gain = [], [], []
    for L in distances_km:
        rng = np.random.default_rng(seed)
        _g, sched, det, _amzi = build_bb84_slice(length_km=float(L), locked=True)
        recs = sched.run(
            n_ticks=n_ticks, dt_slow=1e-3, pulses_per_tick=pulses_per_tick, rng=rng
        )
        last = recs[-1]
        qber.append(last["qber"])
        skr.append(last["skr"])
        gain.append(last["gain"])
    return np.array(qber), np.array(skr), np.array(gain)


def timeseries(length_km=25.0, *, locked=True, pulses_per_tick=60_000, n_ticks=1500, seed=7):
    rng = np.random.default_rng(seed)
    _g, sched, _det, _amzi = build_bb84_slice(length_km=length_km, locked=locked)
    recs = sched.run(
        n_ticks=n_ticks, dt_slow=1e-3, pulses_per_tick=pulses_per_tick, rng=rng
    )
    t = np.array([r["t"] for r in recs])
    q = np.array([r["inst_qber"] for r in recs])
    phase = np.array([r["phase_resid"] for r in recs])
    return t, q, phase


def main() -> None:
    prof = load_default_profile()
    print(f"[M0] profile: {prof.name}")
    print(f"[M0] eta_det={prof.value('eta_det')} (src: {prof.source('eta_det')})")
    print(f"[M0] p_dark={prof.value('p_dark')}/gate (src: {prof.source('p_dark')})\n")

    # --- 1) distance sweep ------------------------------------------------
    distances = np.arange(5, 181, 10.0)
    qber, skr, gain = sweep_distance(distances)

    print("  L(km)    QBER      SKR(bps)")
    for L, q, s in zip(distances, qber, skr):
        if L % 25 == 0 or L == 5:
            print(f"  {L:5.0f}   {q*100:6.2f}%   {s:10.3g}")

    fig, ax1 = plt.subplots(figsize=(7, 4.2))
    ax1.plot(distances, qber * 100, "o-", color="#c0392b", label="QBER")
    ax1.axhline(11.0, ls=":", color="#c0392b", alpha=0.5, label="~11% BB84 threshold")
    ax1.set_xlabel("Fiber length (km)")
    ax1.set_ylabel("QBER (%)", color="#c0392b")
    ax1.set_ylim(0, 25)
    ax2 = ax1.twinx()
    skr_plot = np.where(skr > 0, skr, np.nan)
    ax2.semilogy(distances, skr_plot, "s-", color="#2471a3", label="secret-key rate")
    ax2.set_ylabel("Secret-key rate (bps, log)", color="#2471a3")
    ax1.set_title("M0: decoy-BB84 reference slice — QBER & SKR vs distance")
    fig.tight_layout()
    p1 = os.path.join(FIGDIR, "qber_skr_vs_distance.png")
    fig.savefig(p1, dpi=130)
    print(f"\n[M0] wrote {p1}")

    # --- 2) time-series: phase drift, lock OFF vs ON ----------------------
    t_u, q_u, ph_u = timeseries(locked=False)
    t_l, q_l, ph_l = timeseries(locked=True)

    fig, (axa, axb) = plt.subplots(2, 1, figsize=(7, 5.2), sharex=True)
    axa.plot(t_u, ph_u, color="#7f8c8d", lw=0.8)
    axa.plot(t_l, ph_l, color="#27ae60", lw=0.8)
    axa.set_ylabel("AMZI residual\nphase (rad)")
    axa.set_title("M0: slow phase drift modulating fast batches (multi-rate engine)")
    axb.plot(t_u, q_u * 100, color="#7f8c8d", lw=0.9, label="phase-lock OFF")
    axb.plot(t_l, q_l * 100, color="#27ae60", lw=0.9, label="phase-lock ON")
    axb.set_xlabel("time (s)")
    axb.set_ylabel("instantaneous\nQBER (%)")
    axb.legend(loc="upper right")
    fig.tight_layout()
    p2 = os.path.join(FIGDIR, "qber_timeseries.png")
    fig.savefig(p2, dpi=130)
    print(f"[M0] wrote {p2}")
    print(
        f"[M0] mean QBER: lock OFF = {q_u.mean()*100:.2f}%  |  lock ON = {q_l.mean()*100:.2f}%"
    )


if __name__ == "__main__":
    main()
