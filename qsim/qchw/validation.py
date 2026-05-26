"""Two-tier validation for the qchw plugin — the M4 credibility evidence.

Tier 1 (validate_lindblad): the numeric Lindblad propagator vs closed-form qubit dynamics
(T1 amplitude decay, T2 coherence decay, undamped Rabi) — the backend-correctness gate, the
analog of M0's brute-force check and M3's analytic-Bloch check.

Tier 2 (validate_rb): Randomized Benchmarking recovers the gate error. The RB-fitted
error-per-Clifford must match the INDEPENDENTLY-computed average gate infidelity of the
injected T1/T2 relaxation channel (qchw.backend.avg_gate_infidelity, an exact Pauli-transfer-
matrix quantity). Non-circular: the sampling+exponential-fit pipeline reproduces a number it
never sees. RB is the industry-standard hardware metric [Magesan et al. 2011/2012], so this
is the M1-Rusca-figure analog for the QC-hardware domain.

Note: RB sequence lengths must be scaled to the error (m up to ~ln2/r) or the A*p^m+B fit is
ill-conditioned (p ~ 1 barely decays) and biases the EPC high — `validate_rb` auto-scales.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .backend import DensityMatrixBackend, X
from .rb import run_rb


# ---------------------------------------------------------------------------
# Tier 1 — Lindblad propagator vs closed-form qubit dynamics
# ---------------------------------------------------------------------------
@dataclass
class LindbladCheck:
    err_T1: float       # |numeric P1 - e^{-t/T1}|
    err_T2: float       # |numeric |rho01| - 0.5 e^{-t/T2}|
    err_rabi: float     # |numeric P1 - sin^2(Omega t/2)|
    max_abs_err: float


def validate_lindblad(*, T1: float = 50e-6, T2: float = 30e-6, t: float = 20e-6,
                      Omega: float = 2 * np.pi * 1e6, t_rabi: float = 0.3e-6) -> LindbladCheck:
    # T1: start |1>, expect population e^{-t/T1}
    be = DensityMatrixBackend(1, T1=T1, T2=2 * T1)   # T2=2T1 -> no pure dephasing
    rho = be.evolve(be.ket_density(np.array([0, 1])), t)
    err_T1 = abs(be.populations(rho)[1] - np.exp(-t / T1))

    # T2: start |+>, expect coherence 0.5 e^{-t/T2}
    be = DensityMatrixBackend(1, T1=T1, T2=T2)
    psi = np.array([1, 1]) / np.sqrt(2)
    rho = be.evolve(be.ket_density(psi), t)
    err_T2 = abs(abs(rho[0, 1]) - 0.5 * np.exp(-t / T2))

    # undamped Rabi: H=(Omega/2)X, expect P1 = sin^2(Omega t/2)
    be = DensityMatrixBackend(1)
    rho = be.evolve(be.zero_state(), t_rabi, Hop=(Omega / 2) * X)
    err_rabi = abs(be.populations(rho)[1] - np.sin(Omega * t_rabi / 2) ** 2)

    return LindbladCheck(err_T1=err_T1, err_T2=err_T2, err_rabi=err_rabi,
                         max_abs_err=max(err_T1, err_T2, err_rabi))


# ---------------------------------------------------------------------------
# Tier 2 — RB error-per-Clifford vs analytic channel infidelity
# ---------------------------------------------------------------------------
@dataclass
class RBCheck:
    epc: float                  # RB-fitted error per Clifford
    analytic_infidelity: float  # exact avg gate infidelity of the injected channel
    ratio: float                # epc / analytic
    p: float
    n_lengths: int
    n_seq: int


def validate_rb(*, T1: float = 50e-6, T2: float = 40e-6, t_gate: float = 30e-9,
                n_seq: int = 80, n_lengths: int = 9, seed: int = 2) -> RBCheck:
    be = DensityMatrixBackend(1, T1=T1, T2=T2)
    r_an = be.avg_gate_infidelity(be.relax_channel_matrix(t_gate))
    m_max = max(8, int(0.7 / r_an))        # span a good decay range so the fit is conditioned
    lengths = np.unique(np.linspace(1, m_max, n_lengths).astype(int))
    res = run_rb(T1=T1, T2=T2, t_gate=t_gate, lengths=lengths, n_seq=n_seq, seed=seed)
    return RBCheck(epc=res.epc, analytic_infidelity=r_an, ratio=res.epc / r_an,
                   p=res.p, n_lengths=len(lengths), n_seq=n_seq)
