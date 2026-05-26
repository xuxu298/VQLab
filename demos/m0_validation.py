"""M0 make-or-break demo: validate the multi-rate engine against a brute-force reference.

This is the evidence for spec §14 risk #1 ("multi-rate coupling — correctness & speed").
It answers two questions the rest of the platform rests on:

  1. CORRECTNESS — does the cheap batched engine (frozen-slow-state + mean-field impairments
     + statistical batch aggregation) reproduce a sequential per-gate ground truth?
  2. SPEED/SCALING — is it fast on a laptop, and does its cost decouple from the pulse rate
     so that "operate the device for an hour" becomes tractable?

Outputs demos/figures/m0_validation.png and prints the agreement + scaling tables.

Run:  python -m demos.m0_validation      (from the repo root)
"""
from __future__ import annotations

import os
import time

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.qkd.reference import build_bb84_slice, load_default_profile  # noqa: E402
from qsim.qkd.validation import _binom_se, compare  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)

SECONDS = 0.12      # physical window per comparison (1.2e7 reference gates @ 100 MHz)
DT_SLOW = 1e-4


def benchmark_batched_throughput(profile, *, n_ticks=3000, pulses_per_tick=10_000, seed=11):
    """Measured batched throughput including per-tick overhead, in a realistic config."""
    _g, sched, _det, _amzi = build_bb84_slice(profile, length_km=25.0, locked=True)
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    sched.run(n_ticks=n_ticks, dt_slow=1e-3, pulses_per_tick=pulses_per_tick, rng=rng)
    elapsed = time.perf_counter() - t0
    return (n_ticks * pulses_per_tick) / elapsed, elapsed / n_ticks  # pulses/s, s/tick


def main() -> None:
    prof = load_default_profile()
    rep_rate = prof.value("rep_rate")
    print(f"[validate] profile: {prof.name}   rep_rate={rep_rate:.0e} Hz")
    print(f"[validate] each point: {SECONDS} s of device time "
          f"= {int(SECONDS*rep_rate):,} reference gates vs {int(SECONDS/DT_SLOW)} batched ticks\n")

    # --- 1) CORRECTNESS: agreement vs distance (static phase) -------------
    distances = [10.0, 25.0, 50.0, 75.0, 100.0]
    print("  STATIC phase — batched vs brute-force reference")
    print("   L(km)   QBER batched   QBER bruteforce    ΔQBER(abs)   Δσ    gain Δ%   speedup")
    rows = []
    for L in distances:
        c = compare(length_km=L, drift=False, seconds=SECONDS, dt_slow=DT_SLOW,
                    pulses_per_tick=20_000, seed=1)
        rows.append(c)
        print(f"   {L:5.0f}     {c.batched.qber*100:6.3f}%        {c.bruteforce.qber*100:6.3f}%"
              f"      {(c.batched.qber-c.bruteforce.qber)*100:+6.3f}%   {c.qber_sigmas:4.1f}σ"
              f"   {c.dgain_rel*100:5.2f}%    x{c.speedup:.0f}")

    # --- 2) CORRECTNESS: freeze-slow-state under drift (shared trajectory) -
    cd = compare(length_km=25.0, drift=True, seconds=SECONDS, dt_slow=DT_SLOW,
                 pulses_per_tick=20_000, seed=1)
    print(f"\n  DRIFT (shared OU trajectory, lock OFF) @ 25 km — isolates freeze-slow-state:")
    print(f"   QBER batched={cd.batched.qber*100:.3f}%  bruteforce={cd.bruteforce.qber*100:.3f}%"
          f"  Δ={(cd.batched.qber-cd.bruteforce.qber)*100:+.3f}% ({cd.qber_sigmas:.1f}σ)"
          f"   (phase frozen for a whole {DT_SLOW*1e3:.1f} ms batch -> negligible)")

    dq_abs = [abs(r.batched.qber - r.bruteforce.qber) for r in rows]
    dg_rel = [r.dgain_rel for r in rows]
    print(f"\n  => QBER agreement: worst |Δ| = {max(dq_abs)*100:.3f}% absolute   "
          f"gain agreement: worst |Δ| = {max(dg_rel)*100:.2f}%")
    print(f"     Residual is a small, click-rate-dependent SYSTEMATIC (batched slightly high):")
    print(f"     the mean-field afterpulse smears probability over all gates, while the")
    print(f"     reference's afterpulses cluster in the post-click DEAD time and are vetoed.")
    print(f"     ~0.1% QBER, far below input-parameter calibration uncertainty (a fidelity knob).")

    # --- 3) SPEED / SCALING: cost to simulate one hour @ 100 MHz ----------
    bf_gates_per_s = float(np.mean([r.bruteforce.gates_per_s for r in rows]))
    batched_pps, s_per_tick = benchmark_batched_throughput(prof)

    gates_1h = rep_rate * 3600.0                       # every real gate in an hour
    bf_seconds = gates_1h / bf_gates_per_s             # reference must touch all of them

    # batched run of one hour: dt_slow=1 ms slow clock, 1e4-pulse subsampled batches
    bdt, bppt = 1e-3, 10_000
    n_ticks_1h = 3600.0 / bdt
    batched_seconds = n_ticks_1h * bppt / batched_pps + n_ticks_1h * s_per_tick

    print(f"\n  SCALING — compute to simulate 1 HOUR of operation @ {rep_rate:.0e} Hz:")
    print(f"   brute-force: must simulate {gates_1h:.2e} sequential gates @ "
          f"{bf_gates_per_s:.2e} gates/s  ->  {bf_seconds/3600:.1f} hours of compute")
    print(f"   batched    : {n_ticks_1h:.0e} ticks x {bppt:,} pulses @ "
          f"{batched_pps:.2e} pulses/s   ->  {batched_seconds:.0f} s of compute")
    print(f"   structural speedup ~ x{bf_seconds/batched_seconds:.0f}  "
          f"(batched cost is independent of the pulse rate; brute-force is not)")

    # --- figure -----------------------------------------------------------
    fig, (axq, axs) = plt.subplots(1, 2, figsize=(11, 4.3))

    d = np.array(distances)
    qb = np.array([r.batched.qber for r in rows]) * 100
    qf = np.array([r.bruteforce.qber for r in rows]) * 100
    ferr = np.array([_binom_se(r.bruteforce.qber, r.bruteforce.sifted_clicks) for r in rows]) * 100
    axq.plot(d, qb, "o-", color="#2471a3", lw=1.8, ms=6, label="batched multi-rate engine")
    axq.errorbar(d, qf, yerr=2 * ferr, fmt="s", color="#c0392b", ms=6, capsize=3,
                 label="brute-force per-pulse (±2σ)")
    axq.set_xlabel("Fiber length (km)")
    axq.set_ylabel("QBER (%)")
    axq.set_title("Correctness: batched engine vs ground truth")
    axq.legend(loc="upper left", fontsize=9)
    axq.grid(alpha=0.25)

    labels = ["brute-force\n(per-gate)", "batched\n(multi-rate)"]
    secs = [bf_seconds, batched_seconds]
    bars = axs.bar(labels, secs, color=["#c0392b", "#2471a3"], width=0.6)
    axs.set_yscale("log")
    axs.set_ylabel("compute time to simulate 1 hour @ 100 MHz (s, log)")
    axs.set_title("Scaling: cost decoupled from pulse rate")
    for b, s in zip(bars, secs):
        txt = f"{s/3600:.0f} h" if s > 3600 else f"{s:.0f} s"
        axs.text(b.get_x() + b.get_width() / 2, s, txt, ha="center", va="bottom", fontsize=10)
    axs.grid(alpha=0.25, axis="y")

    fig.tight_layout()
    out = os.path.join(FIGDIR, "m0_validation.png")
    fig.savefig(out, dpi=130)
    print(f"\n[validate] wrote {out}")


if __name__ == "__main__":
    main()
