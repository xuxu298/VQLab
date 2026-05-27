"""Run the Alice gain-switch driver SPICE netlist and the laser rate-equation model (H3).

Mirrors the H1 ngspice loop: ngspice gives the electrical INJECTION CURRENT into the laser; a
two-rate-equation single-mode laser model (carrier number N, photon number S) turns that into the
OPTICAL pulse. It quantifies the three things that matter for decoy-BB84:

  * optical pulse width (FWHM)            -> must be < 500 ps and fit inside the gate period,
  * turn-on jitter                        -> from the driver current noise (low jitter = the moat),
  * the off-state between pulses          -> the field must fully decay so each pulse builds from
                                             spontaneous emission => RANDOM optical phase (security).

Run:  python -m hardware.alice_laser_driver.simulate   (repo root)   or   python simulate.py
"""
from __future__ import annotations

import os
import subprocess

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CIR = os.path.join(HERE, "alice_driver.cir")
DATA = os.path.join(HERE, "alice_driver.data")
FIGDIR = os.path.join(HERE, "..", "..", "demos", "figures")

# --- two-rate-equation 1550 nm DFB laser (number form), tuned for Ith ~ 12 mA ---------------
Q = 1.602e-19
TAU_N = 1.0e-9        # carrier lifetime (s)
TAU_P = 2.0e-12       # photon lifetime (s)
GAMMA = 0.3           # optical confinement factor
G_N = 3.71e4          # gain coefficient (per carrier number, s^-1)
N0 = 3.0e7            # transparency carrier number
EPS = 5.0e-8          # gain compression (per photon number)
BETA = 1.0e-4         # spontaneous-emission coupling
FREP = 1.25e9
ITH = Q * (N0 + 1.0 / (GAMMA * G_N * TAU_P)) / TAU_N   # threshold current (A)


def run_ngspice() -> None:
    subprocess.run(["ngspice", "-b", CIR], cwd=HERE, capture_output=True, text=True)
    if not os.path.exists(DATA):
        raise RuntimeError("ngspice produced no data file; is ngspice installed?")


def load_drive():
    d = np.loadtxt(DATA)
    return d[:, 0], d[:, 1]          # t (s), i_laser (A)


def solve_rate_eqs(t_spice, i_spice, dt=5e-14, i_scale=1.0):
    """RK4-integrate (N, S) over the SPICE window, driven by the injection current. Returns
    (t, S, N) on the uniform grid. `i_scale` perturbs the current (for jitter sensitivity)."""
    t0, t1 = t_spice[0], t_spice[-1]
    t = np.arange(t0, t1, dt)
    I = i_scale * np.interp(t, t_spice, i_spice)
    N = np.empty_like(t)
    S = np.empty_like(t)
    N[0] = max(i_spice[0], 1e-6) * TAU_N / Q     # bias-point carrier number
    S[0] = 1.0                                   # one spontaneous seed photon

    def deriv(n, s, ii):
        g = G_N * (n - N0) / (1.0 + EPS * s)
        dn = ii / Q - n / TAU_N - g * s
        ds = GAMMA * g * s - s / TAU_P + BETA * n / TAU_N
        return dn, ds

    for k in range(len(t) - 1):
        n, s, ii = N[k], S[k], I[k]
        im = 0.5 * (I[k] + I[k + 1])
        k1n, k1s = deriv(n, s, ii)
        k2n, k2s = deriv(n + 0.5 * dt * k1n, s + 0.5 * dt * k1s, im)
        k3n, k3s = deriv(n + 0.5 * dt * k2n, s + 0.5 * dt * k2s, im)
        k4n, k4s = deriv(n + dt * k3n, s + dt * k3s, I[k + 1])
        N[k + 1] = n + dt / 6 * (k1n + 2 * k2n + 2 * k3n + k4n)
        S[k + 1] = max(s + dt / 6 * (k1s + 2 * k2s + 2 * k3s + k4s), 1e-6)
    return t, S, N


DRIVE_PHASE = 0.15            # drive pulse starts at 0.15 of each rep period (matches the .cir)


def drive_start(k: int) -> float:
    return (DRIVE_PHASE + k) / FREP


def pulse_metrics(t, S, k: int = 1):
    """FWHM (s) and peak time (s) of the optical pulse in rep period `k`. Period 0 carries the
    spontaneous-seed start transient, so a later (steady) period is the representative pulse."""
    period = 1.0 / FREP
    win = (t >= drive_start(k)) & (t < drive_start(k) + period)
    tw, sw = t[win], S[win]
    pk = sw.argmax()
    half = 0.5 * sw[pk]
    left = pk
    while left > 0 and sw[left] > half:
        left -= 1
    right = pk
    while right < len(sw) - 1 and sw[right] > half:
        right += 1
    return (tw[right] - tw[left]), tw[pk]


def analyze() -> dict:
    """Run ngspice + the laser model and return the design metrics (no printing/plotting)."""
    run_ngspice()
    t_sp, i_sp = load_drive()
    bias = i_sp[t_sp < 0.1e-9].mean()
    t, S, N = solve_rate_eqs(t_sp, i_sp)
    k = 1                                          # analyse a steady period (period 0 = seed transient)
    fwhm, t_peak = pulse_metrics(t, S, k)
    turn_on = t_peak - drive_start(k)              # drive edge -> optical peak

    # turn-on jitter from driver current noise: sensitivity d(t_peak)/dI x current-noise RMS
    sigma_I = 0.1e-3            # driver injection-current noise (RMS), a low-noise driver
    dI = 0.02 * abs(i_sp.max())
    _, S2, _ = solve_rate_eqs(t_sp, i_sp, i_scale=1.0 + dI / abs(i_sp.max()))
    _, t_peak2 = pulse_metrics(t, S2, k)
    jitter = abs(t_peak2 - t_peak) / dI * sigma_I

    # phase-randomisation check: on/off ratio (peak vs the minimum before the next pulse)
    period = 1.0 / FREP
    between = (t > t_peak + 0.2 * period) & (t < t_peak + 0.9 * period)
    in_period = (t >= drive_start(k)) & (t < drive_start(k) + period)
    on_off = S[in_period].max() / max(S[between].min(), 1e-6)
    return {"t_sp": t_sp, "i_sp": i_sp, "t": t, "S": S, "bias": bias, "sigma_I": sigma_I,
            "fwhm_ps": fwhm * 1e12, "turn_on_ps": turn_on * 1e12, "jitter_ps": jitter * 1e12,
            "on_off": on_off, "ith_ma": ITH * 1e3, "i_peak_ma": i_sp.max() * 1e3}


def main():
    d = analyze()
    t_sp, i_sp, t, S = d["t_sp"], d["i_sp"], d["t"], d["S"]
    bias, sigma_I, fwhm = d["bias"], d["sigma_I"], d["fwhm_ps"] * 1e-12
    turn_on, jitter, on_off = d["turn_on_ps"] * 1e-12, d["jitter_ps"] * 1e-12, d["on_off"]

    print("Alice gain-switch laser driver  (electrical SPICE -> laser rate equations)")
    print(f"  threshold current Ith   : {ITH*1e3:.1f} mA")
    print(f"  DC bias current         : {bias*1e3:.1f} mA  ({'below' if bias<ITH else 'ABOVE'} threshold)")
    print(f"  peak injection current  : {i_sp.max()*1e3:.1f} mA")
    print(f"  optical pulse FWHM      : {fwhm*1e12:.1f} ps   ({'<500 ps OK' if fwhm<500e-12 else 'TOO WIDE'})")
    print(f"  turn-on delay           : {turn_on*1e12:.1f} ps")
    print(f"  driver-noise jitter     : {jitter*1e12:.2f} ps  (from {sigma_I*1e3:.2f} mA RMS current "
          f"noise; the physical floor is spontaneous-emission turn-on jitter, ~few ps)")
    print(f"  on/off ratio (phase rnd): {on_off:.1e}  ({'field resets -> random phase' if on_off>1e3 else 'WARN: residual field'})")
    print(f"  fits in {1/FREP*1e12:.0f} ps gate period: {fwhm < 1/FREP}")

    # figure
    os.makedirs(FIGDIR, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    ax1.plot(t_sp * 1e9, i_sp * 1e3, color="#2471a3", lw=1.5)
    ax1.axhline(ITH * 1e3, color="#c0392b", ls="--", lw=1, label=f"Ith = {ITH*1e3:.0f} mA")
    ax1.set_ylabel("injection current (mA)")
    ax1.set_title("Alice gain-switch driver (H3): electrical drive -> optical pulse")
    ax1.legend(loc="upper right"); ax1.grid(alpha=0.25)
    ax2.semilogy(t * 1e9, S, color="#117a65", lw=1.5)
    ax2.set_ylabel("photon number S (log)")
    ax2.set_xlabel("time (ns)")
    ax2.set_title(f"optical pulse: FWHM {fwhm*1e12:.0f} ps, jitter {jitter*1e12:.1f} ps, "
                  f"on/off {on_off:.0e}")
    ax2.grid(alpha=0.25, which="both")
    fig.tight_layout()
    out = os.path.join(FIGDIR, "h3_gainswitch.png")
    fig.savefig(out, dpi=130)
    print(f"  wrote figure            : {out}")
    return {"fwhm_ps": fwhm * 1e12, "jitter_ps": jitter * 1e12, "on_off": on_off,
            "turn_on_ps": turn_on * 1e12, "ith_ma": ITH * 1e3}


if __name__ == "__main__":
    main()
