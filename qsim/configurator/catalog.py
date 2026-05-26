"""Variant catalog — the parts/subsystem options the configurator chooses among.

Covers the full Alice→fiber→Bob link. Each variant bundles (a) the behavioural-sim parameters
it implies and (b) the hardware it pulls in (BOM lines + flags that drive board-parameter
derivation). This is the 'data' the configurator selects from; adding an option = adding a dict
entry, no new code. Part numbers / performance track docs/01 (architecture+BOM) and docs/03.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ALICE, BOB, SHARED = "Alice", "Bob", "shared"


@dataclass
class BomLine:
    ref: str
    part: str
    side: str = SHARED
    qty_per_channel: int = 0      # scales with n_channels
    qty_per_board: int = 0        # fixed per device side
    unit_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Bob — detector variants
# ---------------------------------------------------------------------------
@dataclass
class DetectorVariant:
    key: str
    label: str
    eta: float                    # detection efficiency (PDE)
    p_dark_per_gate: float        # dark-count probability per gate, per detector
    tau_dead: float               # dead time (s)
    jitter_ps: float              # timing jitter (FWHM)
    max_gate_rate_hz: float
    needs_self_differencing: bool
    polarization_sensitive: bool
    needs_cryostat: bool
    bom: list[BomLine] = field(default_factory=list)


DETECTORS: dict[str, DetectorVariant] = {
    "ingaas_sd": DetectorVariant(
        key="ingaas_sd", label="InGaAs/InP SPAD, self-differencing gated (Phase 1)",
        eta=0.30, p_dark_per_gate=8e-7, tau_dead=3e-9, jitter_ps=90.0,
        max_gate_rate_hz=1.25e9,
        needs_self_differencing=True, polarization_sensitive=False, needs_cryostat=False,
        bom=[
            BomLine("D",   "InGaAs/InP SPAD (Laser Components IAG-series)", BOB, qty_per_channel=1, unit_cost_usd=8000),
            BomLine("SDB", "self-differencing front-end board (docs/03)",   BOB, qty_per_channel=1, unit_cost_usd=1500),
            BomLine("U6",  "AD5535B HV bias DAC",                            BOB, qty_per_board=1,   unit_cost_usd=300),
            BomLine("TEC", "ADN8834 TEC controller + Peltier",              BOB, qty_per_channel=1, unit_cost_usd=120),
        ],
    ),
    "snspd": DetectorVariant(
        key="snspd", label="SNSPD system (upgrade) — superconducting nanowire",
        eta=0.90, p_dark_per_gate=1e-8, tau_dead=0.0, jitter_ps=25.0,
        max_gate_rate_hz=1e10,
        needs_self_differencing=False, polarization_sensitive=True, needs_cryostat=True,
        bom=[
            BomLine("SNS", "SNSPD detector channel (Single Quantum / IDQ class)", BOB, qty_per_channel=1, unit_cost_usd=60000),
            BomLine("CRY", "closed-cycle cryostat 0.8-2.8 K (shared)",            BOB, qty_per_board=1,   unit_cost_usd=180000),
            BomLine("RFA", "uA bias + cryo/RT RF readout",                        BOB, qty_per_channel=1, unit_cost_usd=4000),
            BomLine("POL", "polarization controller (SNSPD is pol-sensitive)",    BOB, qty_per_channel=1, unit_cost_usd=2000),
        ],
    ),
}


# ---------------------------------------------------------------------------
# Alice — source & QRNG variants
# ---------------------------------------------------------------------------
@dataclass
class SourceVariant:
    key: str
    label: str
    max_rep_rate_hz: float
    jitter_ps: float
    bom: list[BomLine] = field(default_factory=list)


SOURCES: dict[str, SourceVariant] = {
    "gainswitched_dfb": SourceVariant(
        key="gainswitched_dfb", label="gain-switched DFB laser @1550 nm",
        max_rep_rate_hz=2.5e9, jitter_ps=20.0,
        bom=[
            BomLine("A1",  "DFB laser (Eblana EP1550-DM), gain-switched", ALICE, qty_per_board=1, unit_cost_usd=800),
            BomLine("AE2", "fast gain-switch laser driver (iC-HG class)", ALICE, qty_per_board=1, unit_cost_usd=200),
            BomLine("AE6", "laser TEC controller (ADN8834)",             ALICE, qty_per_board=1, unit_cost_usd=80),
        ],
    ),
}


@dataclass
class QrngVariant:
    key: str
    label: str
    min_entropy: float            # bits per raw bit (randomness quality)
    bom: list[BomLine] = field(default_factory=list)


QRNGS: dict[str, QrngVariant] = {
    "quantis": QrngVariant(
        key="quantis", label="ID Quantique Quantis (chip/module)", min_entropy=0.99,
        bom=[BomLine("AE5", "QRNG module (IDQ Quantis)", ALICE, qty_per_board=1, unit_cost_usd=1500)]),
    "vacuum": QrngVariant(
        key="vacuum", label="vacuum-fluctuation QRNG (homodyne)", min_entropy=0.95,
        bom=[BomLine("AE5", "vacuum-fluctuation QRNG (custom homodyne)", ALICE, qty_per_board=1, unit_cost_usd=900)]),
}


# Alice encoder (time-bin/phase): intensity modulator + phase encoder + bias controller.
ENCODER_BOM: dict[str, list[BomLine]] = {
    "amzi_timebin": [
        BomLine("A2",  "intensity modulator MZM (EOSPACE/Exail, ER>30dB)", ALICE, qty_per_board=1, unit_cost_usd=5000),
        BomLine("A3",  "phase/time-bin encoder (Exail MPZ-LN / Kylia AMZI)", ALICE, qty_per_board=1, unit_cost_usd=6000),
        BomLine("AE3", "modulator RF driver (broadband)",                   ALICE, qty_per_board=1, unit_cost_usd=1200),
        BomLine("AE4", "MZM bias controller (auto dither-lock)",            ALICE, qty_per_board=1, unit_cost_usd=1500),
    ],
}

# Alice support electronics/optics common to the transmitter.
ALICE_COMMON_BOM: list[BomLine] = [
    BomLine("A4",  "variable optical attenuator (calibrated, -> single photon)", ALICE, qty_per_board=1, unit_cost_usd=1500),
    BomLine("A5",  "optical isolator (>30 dB, Trojan-horse block)",              ALICE, qty_per_board=1, unit_cost_usd=400),
    BomLine("A6",  "monitor PD (InGaAs PIN, decoy calibration)",                 ALICE, qty_per_board=1, unit_cost_usd=200),
    BomLine("AE1", "timing/pattern FPGA (Kintex-7 / ECP5)",                      ALICE, qty_per_board=1, unit_cost_usd=2000),
    BomLine("AE7", "OCXO clock + clean DC rails (low jitter)",                   ALICE, qty_per_board=1, unit_cost_usd=300),
]

# Bob optics/electronics common to both detector variants.
BOB_COMMON_BOM: list[BomLine] = [
    BomLine("B2",   "decoding AMZI (Kylia, phase-stabilised, matched to A3)", BOB, qty_per_board=1, unit_cost_usd=7000),
    BomLine("B3",   "DWDM 100 GHz bandpass filter",                           BOB, qty_per_board=1, unit_cost_usd=500),
    BomLine("BE",   "TDC/time-tagger + FPGA + AMZI phase-lock",               BOB, qty_per_board=1, unit_cost_usd=6000),
    BomLine("B1",   "polarization controller (fiber drift)",                  BOB, qty_per_board=1, unit_cost_usd=1500),
]

# Shared link infrastructure (sync + classical channel).
LINK_BOM: list[BomLine] = [
    BomLine("SYNC", "1310 nm sync TX/RX (PIN + clock recovery), CWDM-combined", SHARED, qty_per_board=1, unit_cost_usd=1500),
    BomLine("CLS",  "classical channel: Gigabit Ethernet (SFP), authenticated", SHARED, qty_per_board=1, unit_cost_usd=400),
]


def catalog_options() -> dict:
    """Variant choices for GUI dropdowns: {field: [{key, label}, ...]}."""
    return {
        "detector": [{"key": k, "label": v.label} for k, v in DETECTORS.items()],
        "source": [{"key": k, "label": v.label} for k, v in SOURCES.items()],
        "qrng": [{"key": k, "label": v.label} for k, v in QRNGS.items()],
        "encoder": [{"key": k, "label": k} for k in ENCODER_BOM],
    }


def derive_board_params(spec, det: DetectorVariant) -> dict:
    """Hardware parameters DERIVED from the spec — the 'turn a knob, the board updates' link."""
    p: dict[str, object] = {}
    # Alice
    p["source_rep_rate_ghz"] = round(spec.gate_rate_hz / 1e9, 3)
    p["modulator_extinction_db"] = spec.modulator_er_db
    p["alice_amzi"] = "ΔL must equal Bob's B2 (matched interferometer)"
    # Bob
    if det.needs_self_differencing:
        p["sd_delay_line_ns"] = round(1e9 / spec.gate_rate_hz, 4)   # = one gate period
        p["bob_readout_path"] = "self-differencing front-end (docs/03)"
    else:
        p["bob_readout_path"] = "uA bias + RF readout (no gating board)"
    p["cooling"] = "closed-cycle cryostat" if det.needs_cryostat else "TEC -30..-40 C"
    p["polarization_control"] = "required (nanowire axis)" if det.polarization_sensitive \
        else "passive (time-bin/phase robust)"
    p["detector_channels"] = spec.n_channels
    # link timing budget
    p["gate_period_ps"] = round(1e12 / spec.gate_rate_hz, 1)
    p["total_jitter_ps"] = round((spec.source_jitter_ps ** 2 + det.jitter_ps ** 2) ** 0.5, 1)
    return p
