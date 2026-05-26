"""Two-tier validation for the sensing plugin — the M3 credibility evidence.

Tier 1 (validate_bloch): the numeric RK4 integrator vs the closed-form Bloch solution.
This is the backend-correctness gate, the analog of M0's "batched engine vs brute-force".

Tier 2 (validate_sensitivity): a Monte-Carlo of the magnetometer estimator vs (a) its exact
per-scheme analytic noise and (b) the published spin-projection-noise limit
    dB_limit = 1 / (gamma * sqrt(N * T2 * t))                       [Budker & Romalis,
    "Optical magnetometry", Nature Physics 3, 227 (2007), Eq. (1)-(2)]
This is the credibility milestone, the analog of M1 matching Rusca's published SKR figure.

Honesty note (Tier 2): 1/(gamma*sqrt(N*T2*t)) is the canonical *scaling* limit. Any concrete
readout carries an O(1) prefactor set by the interrogation time tau and the estimator. For
the Ramsey-style phase estimator modelled here (read both transverse quadratures, each with
1/sqrt(N) projection noise),

    dB(tau) = exp(tau/T2) / (gamma * sqrt(N * tau * t))            (exact, this scheme)

so at tau = T2 the prefactor is e (~2.72) and the optimum tau = T2/2 gives sqrt(2e) (~2.33).
We validate the MC against this exact expression AND confirm the 1/sqrt(N), 1/sqrt(T2),
1/sqrt(t), 1/gamma scaling of the Budker-Romalis limit — we do not pretend to hit the bare
limit, we report the prefactor.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .backend import RB87_GAMMA, SpinEnsembleBackend


# ---------------------------------------------------------------------------
# Tier 1 — integrator vs analytic Bloch solution
# ---------------------------------------------------------------------------
@dataclass
class BlochCheck:
    max_abs_err: float          # max |numeric - analytic| over the sampled trajectory
    larmor_periods: float       # how many Larmor periods the test spanned
    n_steps: int


def validate_bloch(*, Bz: float = 1e-9, T1: float = 0.10, T2: float = 0.05,
                   gamma: float = RB87_GAMMA, periods: float = 5.0, n_samples: int = 40,
                   n_steps_per_sample: int = 50) -> BlochCheck:
    """Integrate a precessing+relaxing spin and compare to the closed form at each sample.

    Start tilted into the transverse plane with a finite z-component so the test exercises
    Larmor precession, T2 decay AND T1 recovery toward the pumped value S0 simultaneously.
    """
    be = SpinEnsembleBackend(gamma=gamma)
    S0_pump = 0.3                       # equilibrium z-polarisation (optical pumping)
    S_start = np.array([1.0, 0.0, 0.8])  # transverse component + initial z offset
    w = gamma * Bz
    period = 2.0 * np.pi / w
    t_end = periods * period
    ts = np.linspace(t_end / n_samples, t_end, n_samples)

    max_err = 0.0
    for t in ts:
        num = be.evolve(S_start, np.array([0.0, 0.0, Bz]), t,
                        T1=T1, T2=T2, S0=S0_pump,
                        n_steps=int(n_steps_per_sample * (t / ts[0])))
        ana = be.evolve_analytic(S_start, Bz, t, T1=T1, T2=T2, S0=S0_pump)
        max_err = max(max_err, float(np.max(np.abs(num - ana))))
    return BlochCheck(max_abs_err=max_err, larmor_periods=periods,
                      n_steps=n_steps_per_sample)


# ---------------------------------------------------------------------------
# Tier 2 — magnetometer sensitivity vs the projection-noise limit
# ---------------------------------------------------------------------------
def estimate_field_once(rng, *, B_true: float, N: float, T2: float, tau: float,
                        gamma: float, n_cycles: int) -> float:
    """One averaged field estimate from `n_cycles` Ramsey-style measurement cycles.

    Each cycle: a unit transverse spin precesses by phi = gamma*B_true*tau and decays to
    amplitude r = exp(-tau/T2); we read both quadratures with independent Gaussian
    projection noise of std 1/sqrt(N), recover the phase by atan2, and convert to a field.
    Averaging n_cycles independent cycles is the device integrating for t = n_cycles*tau.
    """
    r = np.exp(-tau / T2)
    phi = gamma * B_true * tau
    sigma = 1.0 / np.sqrt(N)
    sx = r * np.cos(phi) + rng.normal(0.0, sigma, n_cycles)
    sy = -r * np.sin(phi) + rng.normal(0.0, sigma, n_cycles)
    phi_hat = np.arctan2(-sy, sx)
    return float(np.mean(phi_hat / (gamma * tau)))


def analytic_sensitivity(*, N: float, T2: float, t: float, tau: float,
                         gamma: float) -> float:
    """Exact sensitivity of the modelled estimator: dB = exp(tau/T2)/(gamma*sqrt(N*tau*t))."""
    return np.exp(tau / T2) / (gamma * np.sqrt(N * tau * t))


def projection_noise_limit(*, N: float, T2: float, t: float, gamma: float) -> float:
    """The canonical Budker-Romalis spin-projection-noise limit 1/(gamma*sqrt(N*T2*t))."""
    return 1.0 / (gamma * np.sqrt(N * T2 * t))


@dataclass
class SensitivityCheck:
    emp_sensitivity: float      # Monte-Carlo std of the field estimate (T)
    analytic_sensitivity: float  # exact per-scheme prediction (T)
    bromalis_limit: float       # 1/(gamma*sqrt(N*T2*t)) (T)
    prefactor: float            # emp / bromalis_limit  (the honest O(1) factor)
    rel_err: float              # |emp - analytic| / analytic
    n_trials: int


def validate_sensitivity(*, N: float = 1e6, T2: float = 1e-3, tau: float | None = None,
                         t: float = 1.0, gamma: float = RB87_GAMMA, B_true: float = 0.0,
                         n_trials: int = 4000, seed: int = 0) -> SensitivityCheck:
    """Monte-Carlo the estimator and compare its std to the analytic + published limit.

    tau defaults to T2 (the canonical coherence-time interrogation). t is the total
    integration time, so each trial averages n_cycles = t/tau cycles.
    """
    tau = T2 if tau is None else tau
    n_cycles = max(1, int(round(t / tau)))
    rng = np.random.default_rng(seed)
    ests = np.array([
        estimate_field_once(rng, B_true=B_true, N=N, T2=T2, tau=tau,
                            gamma=gamma, n_cycles=n_cycles)
        for _ in range(n_trials)
    ])
    emp = float(np.std(ests, ddof=1))
    ana = analytic_sensitivity(N=N, T2=T2, t=n_cycles * tau, tau=tau, gamma=gamma)
    lim = projection_noise_limit(N=N, T2=T2, t=n_cycles * tau, gamma=gamma)
    return SensitivityCheck(
        emp_sensitivity=emp,
        analytic_sensitivity=ana,
        bromalis_limit=lim,
        prefactor=emp / lim,
        rel_err=abs(emp - ana) / ana,
        n_trials=n_trials,
    )
