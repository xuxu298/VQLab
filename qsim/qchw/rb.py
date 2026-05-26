"""Randomized Benchmarking (RB) — the standard QC-hardware gate-fidelity protocol.

[Magesan, Gambetta, Emerson, PRL 106, 180504 (2011); PRA 85, 042311 (2012)]

We run length-m sequences of random single-qubit Cliffords, append the recovery Clifford that
ideally returns |0>, and record the survival probability P(0). Averaged over random sequences
it decays as

    F(m) = A * p^m + B,        error-per-Clifford  r = (1 - p) * (d - 1) / d   (d = 2).

Each physical gate is modelled as "ideal Clifford unitary, then a fixed noise channel"
(here the T1/T2 relaxation over the gate duration). The point of M4's Tier-2 validation is
that the RB-fitted r matches the *independently* computed average gate infidelity of that
same noise channel (qchw.backend.avg_gate_infidelity) — a non-circular check that the whole
gate + noise + measurement + fit stack is correct.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .backend import DensityMatrixBackend
from .cliffords import CliffordGroup


def sequence_survival(be: DensityMatrixBackend, group: CliffordGroup, m: int,
                      noise_chan: np.ndarray | None, rng: np.random.Generator) -> float:
    """Exact survival probability P(0) for one random length-m Clifford sequence."""
    idx = group.random_indices(m, rng)
    U_prod = np.eye(2, dtype=complex)
    rho = be.zero_state()
    for i in idx:
        U = group.elements[i]
        rho = be.apply_unitary(rho, U)
        if noise_chan is not None:
            rho = be.apply_channel(rho, noise_chan)
        U_prod = U @ U_prod
    recovery = group.inverse_of_product(U_prod)
    rho = be.apply_unitary(rho, recovery)
    if noise_chan is not None:
        rho = be.apply_channel(rho, noise_chan)
    return be.prob_zero(rho)


@dataclass
class RBResult:
    lengths: np.ndarray
    survival: np.ndarray        # mean survival prob per length
    p: float                    # fitted decay parameter
    A: float
    B: float
    epc: float                  # error per Clifford = (1-p)(d-1)/d


def run_rb(*, T1: float, T2: float, t_gate: float, lengths=None, n_seq: int = 40,
           seed: int = 0) -> RBResult:
    """Simulate RB on a single qubit with T1/T2 relaxation over each gate."""
    lengths = np.array(lengths if lengths is not None else [1, 2, 4, 8, 16, 32, 64, 128])
    be = DensityMatrixBackend(1, T1=T1, T2=T2)
    group = CliffordGroup()
    noise = be.relax_channel_matrix(t_gate)
    rng = np.random.default_rng(seed)

    surv = np.array([
        np.mean([sequence_survival(be, group, int(m), noise, rng) for _ in range(n_seq)])
        for m in lengths
    ])
    p, A, B = fit_rb_decay(lengths, surv)
    return RBResult(lengths=lengths, survival=surv, p=p, A=A, B=B,
                    epc=(1.0 - p) * 0.5)


def fit_rb_decay(lengths: np.ndarray, surv: np.ndarray) -> tuple[float, float, float]:
    """Fit F(m) = A p^m + B. Falls back to a fixed B=0.5 linear fit if SciPy is absent."""
    lengths = np.asarray(lengths, dtype=float)
    surv = np.asarray(surv, dtype=float)
    try:
        from scipy.optimize import curve_fit

        def model(m, A, p, B):
            return A * p ** m + B

        (A, p, B), _ = curve_fit(
            model, lengths, surv, p0=[0.5, 0.99, 0.5],
            bounds=([0.0, 0.0, 0.0], [1.0, 1.0, 1.0]), maxfev=20000,
        )
        return float(p), float(A), float(B)
    except Exception:
        # log-linear fit with the ideal asymptote B = 1/d = 0.5
        y = np.log(np.clip(surv - 0.5, 1e-12, None))
        slope, intercept = np.polyfit(lengths, y, 1)
        return float(np.exp(slope)), float(np.exp(intercept)), 0.5
