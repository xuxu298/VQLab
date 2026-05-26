"""Magnetometer metrics (spec §9 — per-domain metrics).

The headline figure of merit for a magnetometer is its sensitivity expressed as an amplitude
spectral density in T/sqrt(Hz): the field uncertainty after 1 s of averaging. A single
measurement cycle of duration tau gives a per-cycle field uncertainty sigma_cycle; averaging
N_c cycles (total time t = N_c*tau) scales it as 1/sqrt(N_c), so

    dB(t) = sigma_cycle * sqrt(tau / t)   ==>   ASD = dB(t)*sqrt(t) = sigma_cycle*sqrt(tau).

The fundamental floor is the spin-projection-noise limit (Budker & Romalis 2007):
    ASD_limit = 1 / (gamma * sqrt(N * T2))   [T/sqrt(Hz)].
"""
from __future__ import annotations

import numpy as np


def sensitivity_asd(sigma_cycle: float, tau: float) -> float:
    """Amplitude spectral density (T/sqrt(Hz)) from the per-cycle std and cycle time."""
    return sigma_cycle * np.sqrt(tau)


def sensitivity_over_time(sigma_cycle: float, tau: float, t: float) -> float:
    """Field uncertainty (T) after averaging for total time t."""
    return sigma_cycle * np.sqrt(tau / t)


def projection_limit_asd(*, N: float, T2: float, gamma: float) -> float:
    """The spin-projection-noise-limited ASD 1/(gamma*sqrt(N*T2)) [T/sqrt(Hz)]."""
    return 1.0 / (gamma * np.sqrt(N * T2))
