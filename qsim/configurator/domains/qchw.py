"""QC-hardware domain — a noisy few-qubit processor, on the generic configurator.

Uses the fast analytic figures validated in M4 (no Monte-Carlo RB per knob change):
  * average gate infidelity = exact Pauli-transfer-matrix value of the T1/T2 relaxation
    channel over the gate time (== the RB error-per-Clifford in the gate-independent regime);
  * Bell-state fidelity from a direct H+CNOT preparation under the same noise.
"""
from __future__ import annotations

from ...qchw.backend import DensityMatrixBackend
from ...qchw.reference import bell_fidelity_under_noise
from ..catalog import BomLine
from ..registry import Domain, register_domain
from ..report import FAIL, INFO, PASS, WARN, ConfigReport, Metric, assemble_bom, feasible

SCHEMA = [
    {"key": "n_qubits", "label": "Qubits", "type": "select",
     "options": [{"key": 1, "label": "1"}, {"key": 2, "label": "2"}]},
    {"key": "T1_us", "label": "Relaxation T1", "type": "range", "min": 5, "max": 300,
     "step": 5, "unit": "µs"},
    {"key": "T2_us", "label": "Coherence T2", "type": "range", "min": 5, "max": 400,
     "step": 5, "unit": "µs"},
    {"key": "t_gate_ns", "label": "Gate duration", "type": "range", "min": 5, "max": 400,
     "step": 5, "unit": "ns"},
]
DEFAULTS = {"n_qubits": 2, "T1_us": 50.0, "T2_us": 70.0, "t_gate_ns": 40.0}
SWEEP = {"knob": "t_gate_ns", "label": "gate duration (ns)", "metric": "error_per_gate",
         "metric_label": "error per gate", "logy": True, "logx": False,
         "values": [10, 20, 40, 80, 120, 200, 300, 400]}


def configure(knobs: dict) -> ConfigReport:
    n_qubits = int(knobs.get("n_qubits", DEFAULTS["n_qubits"]))
    T1 = float(knobs.get("T1_us", DEFAULTS["T1_us"])) * 1e-6
    T2 = float(knobs.get("T2_us", DEFAULTS["T2_us"])) * 1e-6
    t_gate = float(knobs.get("t_gate_ns", DEFAULTS["t_gate_ns"])) * 1e-9

    bom_lines = [
        BomLine("AWG", "arbitrary-waveform gen / DAC channel (per qubit)", "control", qty_per_channel=1, unit_cost_usd=6000),
        BomLine("RO",  "readout chain (ADC + JPA/TWPA front-end, per qubit)", "readout", qty_per_channel=1, unit_cost_usd=8000),
        BomLine("CTL", "control FPGA + timing (shared)",                "control", qty_per_board=1, unit_cost_usd=15000),
        BomLine("FR",  "dilution refrigerator (~10 mK, shared)",        "cryo", qty_per_board=1, unit_cost_usd=400000),
        BomLine("LNA", "cryogenic LNAs + wiring/attenuators (per qubit)", "cryo", qty_per_channel=1, unit_cost_usd=5000),
    ]
    bom, by_side, total = assemble_bom(bom_lines, n_channels=n_qubits)

    rules = []
    if T2 > 2 * T1 + 1e-15:
        rules.append((FAIL, f"T2 ({T2*1e6:.0f} µs) > 2*T1 ({2*T1*1e6:.0f} µs) is unphysical"))
        metrics = [Metric("gate_fidelity", "Avg gate fidelity", 0.0, "%", "—"),
                   Metric("error_per_gate", "Error per gate", 1.0, "", "—")]
        board = {"note": "fix T2<=2*T1 to evaluate"}
        return ConfigReport(domain="qchw", name="qubit_processor", metrics=metrics, bom=bom,
                            cost_by_side=by_side, bom_total_usd=total, board_params=board,
                            rules=rules, feasible=False,
                            headline_keys=["gate_fidelity", "error_per_gate"])

    be = DensityMatrixBackend(1, T1=T1, T2=T2)
    r = be.avg_gate_infidelity(be.relax_channel_matrix(t_gate))   # == RB error-per-Clifford
    gate_fid = 1.0 - r
    metrics = [
        Metric("gate_fidelity", "Avg gate fidelity", gate_fid * 100, "%", f"{gate_fid*100:.3f} %"),
        Metric("error_per_gate", "Error per gate (RB)", r, "", f"{r:.2e}"),
    ]
    if n_qubits >= 2:
        bell = bell_fidelity_under_noise(T1=T1, T2=T2, t_gate=t_gate)
        metrics.append(Metric("bell_fidelity", "Bell-state fidelity", bell * 100, "%",
                              f"{bell*100:.2f} %"))

    board = {
        "T2/T1_ratio": f"{T2/T1:.2f} (<= 2)",
        "gate/T2_ratio": f"{t_gate/T2:.2e} (smaller = better)",
        "coherence_limit": "gate error set by relaxation over t_gate",
        "entangling_gate": "CNOT" if n_qubits >= 2 else "single-qubit only",
    }
    if gate_fid < 0.99:
        rules.append((WARN, f"gate fidelity {gate_fid*100:.2f}% < 99% — below typical "
                            f"error-correction thresholds; shorten gate or improve T2"))
    if t_gate > 0.05 * T2:
        rules.append((WARN, f"gate time {t_gate*1e9:.0f} ns is not << T2 ({T2*1e6:.0f} µs); "
                            f"relaxation dominates the gate error"))
    rules.append((INFO, "error per gate == the RB error-per-Clifford in the gate-independent "
                        "T1/T2 regime (M4 validation)"))
    if feasible(rules):
        rules.append((PASS, "all hard constraints satisfied"))

    return ConfigReport(domain="qchw", name="qubit_processor", metrics=metrics, bom=bom,
                        cost_by_side=by_side, bom_total_usd=total, board_params=board,
                        rules=rules, feasible=feasible(rules),
                        headline_keys=["gate_fidelity", "error_per_gate", "bell_fidelity"])


register_domain(Domain(name="qchw", label="Qubit processor (QC hardware)", schema=SCHEMA,
                       defaults=DEFAULTS, configure=configure, sweep=SWEEP))
