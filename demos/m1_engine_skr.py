"""M1 capstone demo: engine-driven secret-key rate with the real finite-key bound.

This closes the loop M0->M1: the multi-rate engine (with afterpulsing, slow AMZI phase
drift, dead time) drives the 1-decoy source + sifting detector, accumulates the
per-(basis, intensity) counts, and the Rusca 2018 finite-key bound turns them into a
*proven* secret-key rate. Unlike demos/m1_rusca_validation.py (analytic channel), the
rates here come from the actual simulated device — so effects the channel model omits
(afterpulse noise, phase-lock quality) flow straight into the key rate.

We sweep distance and contrast phase-lock ON vs OFF: with the lock off, the AMZI phase
wanders, the X-basis error inflates, the single-photon phase-error bound rises, and the
proven key collapses — a security consequence of a control-loop choice, shown end-to-end.

Run:  python -m demos.m1_engine_skr
"""
from __future__ import annotations

import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from qsim.qkd.keyrate import skr_from_rates  # noqa: E402
from qsim.qkd.reference import build_decoy_bb84, load_default_profile  # noqa: E402

FIGDIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIGDIR, exist_ok=True)

PROF = load_default_profile()
MU1, MU2 = PROF.value("mu1"), PROF.value("mu2")
P1, PZ, REP = PROF.value("p_mu1"), PROF.value("p_Z"), PROF.value("rep_rate")
N_Z = 1e9     # privacy-amplification block size


def engine_rates(length_km, locked, ticks=400, pulses=150_000, seed=1):
    _g, sched, det, _amzi = build_decoy_bb84(PROF, length_km=length_km, locked=locked)
    sched.run(n_ticks=ticks, dt_slow=1e-3, pulses_per_tick=pulses,
              rng=np.random.default_rng(seed))
    return det.rates()


def main() -> None:
    print("Engine-driven 1-decoy BB84 SKR (Rusca finite-key) — full impairments")
    print(f"  profile={PROF.name}  eta_det={PROF.value('eta_det')}  mu1={MU1} mu2={MU2}  "
          f"n_Z={N_Z:.0e}  R={REP:.0e} Hz\n")

    distances = [10.0, 25.0, 40.0, 60.0, 80.0, 100.0]
    out = {True: [], False: []}
    print("   L(km)   QBER_X lock-on   SKR lock-on     QBER_X lock-off   SKR lock-off")
    for L in distances:
        row = {}
        for locked in (True, False):
            r = engine_rates(L, locked)
            skr, kr = skr_from_rates(r, mu1=MU1, mu2=MU2, p_mu1=P1, p_Z=PZ,
                                     n_Z_block=N_Z, rep_rate=REP)
            out[locked].append(skr)
            row[locked] = (r["E_X1"] * 100, skr)
        print(f"   {L:5.0f}     {row[True][0]:6.2f}%      {row[True][1]:11.3e}       "
              f"{row[False][0]:6.2f}%       {row[False][1]:11.3e}")

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    d = np.array(distances)
    for locked, color, lab in [(True, "#27ae60", "phase-lock ON"),
                               (False, "#c0392b", "phase-lock OFF")]:
        y = np.array(out[locked])
        m = y > 0
        ax.semilogy(d[m], y[m], "o-", color=color, label=lab)
        if not np.all(m):  # mark where the proven key collapses
            ax.semilogy(d[~m], np.full((~m).sum(), 1.0), "x", color=color, alpha=0.6)
    ax.set_xlabel("Fiber length (km)   [0.2 dB/km + Bob optics + det. eff.]")
    ax.set_ylabel("Proven secret-key rate (Hz, log)")
    ax.set_title(f"M1: engine-driven finite-key SKR (n_Z={N_Z:.0e}) — lock ON vs OFF")
    ax.legend()
    ax.grid(alpha=0.25, which="both")
    fig.tight_layout()
    p = os.path.join(FIGDIR, "m1_engine_skr.png")
    fig.savefig(p, dpi=130)
    print(f"\n[M1] wrote {p}")
    print("[M1] phase-lock quality (a control-loop choice) -> X-basis error -> single-photon")
    print("     phase-error bound -> proven key. The whole device stack feeds the security proof.")


if __name__ == "__main__":
    main()
