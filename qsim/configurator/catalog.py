"""Variant catalog — the parts/subsystem options the configurator chooses among.

Each detector variant bundles (a) the behavioural-sim parameters it implies and (b) the
hardware it pulls in (BOM lines + flags that drive board-parameter derivation). This is the
'data' the configurator selects from; adding a new option = adding a dict entry, no new code.
Part numbers and performance match docs/03 (InGaAs self-differencing) and the §4.3 SNSPD
upgrade path in docs/01.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BomLine:
    ref: str
    part: str
    qty_per_channel: int = 0      # scales with n_channels
    qty_per_board: int = 0        # fixed per device side
    unit_cost_usd: float = 0.0


@dataclass
class DetectorVariant:
    key: str
    label: str
    eta: float                    # detection efficiency (PDE)
    p_dark_per_gate: float        # dark-count probability per gate, per detector
    tau_dead: float               # dead time (s)
    max_gate_rate_hz: float       # highest practical gating/operating rate
    needs_self_differencing: bool
    polarization_sensitive: bool
    needs_cryostat: bool
    bom: list[BomLine] = field(default_factory=list)


DETECTORS: dict[str, DetectorVariant] = {
    "ingaas_sd": DetectorVariant(
        key="ingaas_sd",
        label="InGaAs/InP SPAD, self-differencing gated (Phase 1)",
        eta=0.30, p_dark_per_gate=8e-7, tau_dead=3e-9,
        max_gate_rate_hz=1.25e9,
        needs_self_differencing=True, polarization_sensitive=False, needs_cryostat=False,
        bom=[
            BomLine("D",   "InGaAs/InP SPAD (Laser Components IAG-series)", qty_per_channel=1, unit_cost_usd=8000),
            BomLine("SDB", "self-differencing front-end board (docs/03)",   qty_per_channel=1, unit_cost_usd=1500),
            BomLine("U6",  "AD5535B HV bias DAC",                            qty_per_board=1,   unit_cost_usd=300),
            BomLine("TEC", "ADN8834 TEC controller + Peltier",              qty_per_channel=1, unit_cost_usd=120),
        ],
    ),
    "snspd": DetectorVariant(
        key="snspd",
        label="SNSPD system (upgrade) — superconducting nanowire",
        eta=0.90, p_dark_per_gate=1e-8, tau_dead=0.0,
        max_gate_rate_hz=1e10,
        needs_self_differencing=False, polarization_sensitive=True, needs_cryostat=True,
        bom=[
            BomLine("SNS", "SNSPD detector channel (Single Quantum / IDQ class)", qty_per_channel=1, unit_cost_usd=60000),
            BomLine("CRY", "closed-cycle cryostat 0.8-2.8 K (shared)",            qty_per_board=1,   unit_cost_usd=180000),
            BomLine("RFA", "uA bias + cryo/RT RF readout",                        qty_per_channel=1, unit_cost_usd=4000),
            BomLine("POL", "polarization controller (SNSPD is pol-sensitive)",    qty_per_channel=1, unit_cost_usd=2000),
        ],
    ),
}

# Optics/electronics common to both detector variants (per Bob side), representative costs.
COMMON_BOM: list[BomLine] = [
    BomLine("B2", "decoding AMZI (Kylia, phase-stabilised)", qty_per_board=1, unit_cost_usd=7000),
    BomLine("B3", "DWDM 100 GHz bandpass filter",            qty_per_board=1, unit_cost_usd=500),
    BomLine("BE", "TDC/time-tagger + FPGA + AMZI phase-lock", qty_per_board=1, unit_cost_usd=6000),
    BomLine("SYNC", "1310 nm sync RX (PIN + clock recovery)", qty_per_board=1, unit_cost_usd=800),
]


def derive_board_params(spec, variant: DetectorVariant) -> dict:
    """Hardware parameters DERIVED from the spec — the 'turn a knob, the board updates' link."""
    p: dict[str, object] = {}
    if variant.needs_self_differencing:
        # the self-differencing delay line must equal exactly one gate period (docs/03)
        p["sd_delay_line_ns"] = round(1e9 / spec.gate_rate_hz, 4)
        p["readout_path"] = "self-differencing front-end (docs/03)"
    else:
        p["readout_path"] = "uA bias + RF readout (no gating board)"
    p["cooling"] = "closed-cycle cryostat" if variant.needs_cryostat else "TEC -30..-40 C"
    p["polarization_control"] = "required (nanowire axis)" if variant.polarization_sensitive \
        else "passive (time-bin/phase robust)"
    p["detector_channels"] = spec.n_channels
    return p
