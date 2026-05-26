"""QC-hardware metrics (spec §9 — per-domain metrics).

The standard device figures of merit: average gate fidelity / error-per-Clifford from RB, and
the prepared-state (here Bell) fidelity. EPC converts an RB decay p to an error per gate.
"""
from __future__ import annotations


def error_per_clifford(p: float, d: int = 2) -> float:
    """Error per Clifford from the RB decay parameter: r = (1 - p)(d - 1)/d."""
    return (1.0 - p) * (d - 1) / d


def avg_gate_fidelity(p: float, d: int = 2) -> float:
    """Average gate fidelity 1 - r."""
    return 1.0 - error_per_clifford(p, d)
