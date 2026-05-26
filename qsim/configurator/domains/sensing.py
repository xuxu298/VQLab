"""Sensing domain — an optically-pumped atomic magnetometer, on the generic configurator.

Uses the closed-form sensitivity validated in M3 (no Monte-Carlo, so the GUI is instant):
  ASD = exp(tau/T2) * sigma_read / (gamma * sqrt(tau))     [T/sqrt(Hz)]
  projection-noise limit = 1 / (gamma * sqrt(N * T2))      (Budker & Romalis 2007)
with sigma_read = sqrt(1/N + technical_noise^2) the per-quadrature readout noise.
"""
from __future__ import annotations

import numpy as np

from ...sensing.backend import RB87_GAMMA
from ..catalog import BomLine
from ..registry import Domain, register_domain
from ..report import FAIL, INFO, PASS, WARN, ConfigReport, Metric, assemble_bom, feasible

GAMMA = RB87_GAMMA   # Rb-87 gyromagnetic ratio (rad/s/T)

SCHEMA = [
    {"key": "atom_number", "label": "Atom number N", "type": "select",
     "options": [{"key": v, "label": f"{v:.0e}"} for v in (1e10, 1e11, 1e12, 1e13, 1e14)]},
    {"key": "T2_ms", "label": "Coherence time T2", "type": "range", "min": 0.1, "max": 50,
     "step": 0.1, "unit": "ms"},
    {"key": "T1_ms", "label": "Relaxation time T1", "type": "range", "min": 1, "max": 200,
     "step": 1, "unit": "ms"},
    {"key": "tau_ms", "label": "Interrogation time tau", "type": "range", "min": 0.05,
     "max": 20, "step": 0.05, "unit": "ms"},
    {"key": "technical_noise", "label": "Technical readout noise", "type": "range",
     "min": 0.0, "max": 0.01, "step": 0.0005, "unit": ""},
]
DEFAULTS = {"atom_number": 1e12, "T2_ms": 5.0, "T1_ms": 30.0, "tau_ms": 5.0,
            "technical_noise": 0.0}
SWEEP = {"knob": "atom_number", "label": "atom number N", "metric": "sensitivity_asd",
         "metric_label": "sensitivity (T/√Hz)", "logy": True, "logx": True,
         "values": [10 ** e for e in (10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14)]}


def _fT(x: float) -> str:
    return f"{x*1e15:.3f} fT/√Hz"


def configure(knobs: dict) -> ConfigReport:
    N = float(knobs.get("atom_number", DEFAULTS["atom_number"]))
    T1 = float(knobs.get("T1_ms", DEFAULTS["T1_ms"])) * 1e-3
    T2 = float(knobs.get("T2_ms", DEFAULTS["T2_ms"])) * 1e-3
    tau = float(knobs.get("tau_ms", DEFAULTS["tau_ms"])) * 1e-3
    tech = float(knobs.get("technical_noise", DEFAULTS["technical_noise"]))

    sigma_read = np.sqrt(1.0 / N + tech ** 2)
    asd = np.exp(tau / T2) * sigma_read / (GAMMA * np.sqrt(tau))
    limit = 1.0 / (GAMMA * np.sqrt(N * T2))
    ratio = asd / limit

    bom_lines = [
        BomLine("VC",  "alkali (Rb) vapor cell, anti-relaxation coated", "optics", qty_per_board=1, unit_cost_usd=2500),
        BomLine("PMP", "pump laser (DBR @795 nm) + driver",             "optics", qty_per_board=1, unit_cost_usd=3000),
        BomLine("PRB", "probe laser + polarimeter readout",             "optics", qty_per_board=1, unit_cost_usd=3500),
        BomLine("PD",  "balanced photodetector + transimpedance",       "electronics", qty_per_board=1, unit_cost_usd=800),
        BomLine("OVN", "cell heater/oven + temperature control",        "electronics", qty_per_board=1, unit_cost_usd=600),
        BomLine("DAQ", "lock-in / DAQ + control FPGA",                  "electronics", qty_per_board=1, unit_cost_usd=2000),
        BomLine("SH",  "mu-metal magnetic shield (multi-layer)",        "shielding", qty_per_board=1, unit_cost_usd=4000),
        BomLine("COIL","Helmholtz bias/compensation coils + driver",    "shielding", qty_per_board=1, unit_cost_usd=1200),
    ]
    bom, by_side, total = assemble_bom(bom_lines)
    board = {
        "gyromagnetic_ratio": f"{GAMMA/2/np.pi/1e9:.2f} GHz/T (Rb-87)",
        "optimal_tau": f"~T2/2 = {T2*1e3/2:.2f} ms (min sensitivity)",
        "readout_noise_floor": f"projection 1/√N = {1/np.sqrt(N):.2e}",
        "decay_at_tau": f"exp(-tau/T2) = {np.exp(-tau/T2):.3f}",
    }

    rules = []
    if T2 > 2 * T1 + 1e-12:
        rules.append((FAIL, f"T2 ({T2*1e3:.1f} ms) > 2*T1 ({2*T1*1e3:.1f} ms) is unphysical"))
    if tau > 2 * T2:
        rules.append((WARN, f"interrogation tau ({tau*1e3:.1f} ms) >> T2 ({T2*1e3:.1f} ms): "
                            f"signal has decayed (exp(-tau/T2)={np.exp(-tau/T2):.2f}); lower tau"))
    if tech > 1.0 / np.sqrt(N):
        rules.append((WARN, f"technical noise ({tech:.2e}) exceeds projection noise "
                            f"(1/√N={1/np.sqrt(N):.2e}): not quantum-limited"))
    else:
        rules.append((INFO, f"projection-noise-limited (within {ratio:.1f}× the SQL)"))
    if feasible(rules):
        rules.append((PASS, "all hard constraints satisfied"))

    metrics = [
        Metric("sensitivity_asd", "Sensitivity (ASD)", asd, "T/√Hz", _fT(asd)),
        Metric("projection_limit_asd", "Projection-noise limit", limit, "T/√Hz", _fT(limit)),
        Metric("asd_ratio", "× above quantum limit", ratio, "×", f"{ratio:.2f}×"),
    ]
    return ConfigReport(domain="sensing", name="atomic_magnetometer", metrics=metrics,
                        bom=bom, cost_by_side=by_side, bom_total_usd=total,
                        board_params=board, rules=rules, feasible=feasible(rules),
                        headline_keys=["sensitivity_asd", "projection_limit_asd", "asd_ratio"])


register_domain(Domain(name="sensing", label="Atomic magnetometer (sensing)", schema=SCHEMA,
                       defaults=DEFAULTS, configure=configure, sweep=SWEEP))
