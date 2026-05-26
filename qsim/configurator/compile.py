"""Compile a DeviceSpec into a unified configuration: behavioural sim + hardware + rules.

`configure(spec)` is the one call that realises the configurator: from the high-level knobs it
(1) runs qsim's validated finite-key model for QBER/SKR, (2) assembles the BOM and derives the
board parameters from the chosen variant, and (3) runs design-rule checks that tie the two
together. Change one knob -> all three update consistently.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..qkd.channel import ChannelParams, gain_qber
from ..qkd.keyrate import optimize_skr, skr_for_params
from .catalog import COMMON_BOM, DETECTORS, DetectorVariant, derive_board_params
from .spec import DeviceSpec

# severity levels for design-rule findings
PASS, INFO, WARN, FAIL = "PASS", "INFO", "WARN", "FAIL"


@dataclass
class BomItem:
    ref: str
    part: str
    qty: int
    line_cost_usd: float


@dataclass
class ConfigReport:
    spec: DeviceSpec
    variant_label: str
    loss_db: float
    qber: float
    skr_bps: float
    mu1: float
    mu2: float
    bom: list[BomItem]
    bom_total_usd: float
    board_params: dict
    rules: list[tuple[str, str]]          # (level, message)
    feasible: bool

    def format(self) -> str:
        s = self.spec
        lines = [
            f"=== configured device: {s.name} ===",
            f"  protocol/detector : {s.protocol} / {self.variant_label}",
            f"  channels / gate   : {s.n_channels} ch @ {s.gate_rate_hz/1e9:.2f} GHz",
            f"  span / link loss  : {s.distance_km:.0f} km  ->  {self.loss_db:.1f} dB",
            "",
            "  -- behavioural sim (qsim finite-key) --",
            f"    QBER            : {self.qber*100:.2f} %",
            f"    secret-key rate : {self.skr_bps:,.0f} bps"
            + (f" ({self.skr_bps/1e6:.2f} Mbps)" if self.skr_bps >= 1e5 else ""),
            f"    optimal mu1/mu2 : {self.mu1:.3f} / {self.mu2:.3f}",
            "",
            "  -- derived board parameters --",
        ]
        for k, v in self.board_params.items():
            lines.append(f"    {k:<22}: {v}")
        lines += ["", "  -- bill of materials (per device side) --"]
        for it in self.bom:
            lines.append(f"    {it.ref:<5} x{it.qty:<2} {it.part:<48} ${it.line_cost_usd:,.0f}")
        lines.append(f"    {'TOTAL':<5}{'':<3}{'':<48} ${self.bom_total_usd:,.0f}")
        lines += ["", "  -- design rules --"]
        for level, msg in self.rules:
            lines.append(f"    [{level}] {msg}")
        lines.append(f"  => {'FEASIBLE' if self.feasible else 'NOT FEASIBLE'}")
        return "\n".join(lines)


def _channel_params(spec: DeviceSpec, v: DetectorVariant) -> ChannelParams:
    return ChannelParams(eta_det=v.eta, fiber_alpha=spec.fiber_alpha_db_km,
                         p_dc=v.p_dark_per_gate, e_d=spec.e_misalignment, tau_dead=v.tau_dead)


def _simulate(spec: DeviceSpec, v: DetectorVariant) -> tuple[float, float, float, float]:
    """(QBER, SKR_bps, mu1, mu2) from qsim's validated finite-key model."""
    loss = spec.fiber_alpha_db_km * spec.distance_km + spec.bob_insertion_db
    params = _channel_params(spec, v)
    if spec.mu1 is not None and spec.mu2 is not None:
        skr, _ = skr_for_params(loss, spec.n_z_block, spec.mu1, spec.mu2, 0.7, 0.9,
                                rep_rate=spec.gate_rate_hz, params=params,
                                eps_sec=1e-9, eps_cor=1e-15, f_ec=1.16)
        mu1, mu2 = spec.mu1, spec.mu2
    else:
        pt = optimize_skr(loss, spec.n_z_block, rep_rate=spec.gate_rate_hz, params=params,
                          f_ec=1.16, eps_sec=1e-9, eps_cor=1e-15, n_restarts=6)
        skr, mu1, mu2 = pt.skr, pt.mu1, pt.mu2
    eta = v.eta * 10.0 ** (-loss / 10.0)
    _, qber = gain_qber(mu1, eta, v.p_dark_per_gate, spec.e_misalignment)
    return qber, skr, mu1, mu2


def _assemble_bom(spec: DeviceSpec, v: DetectorVariant) -> tuple[list[BomItem], float]:
    items: list[BomItem] = []
    for line in list(v.bom) + COMMON_BOM:
        qty = line.qty_per_channel * spec.n_channels + line.qty_per_board
        if qty == 0:
            continue
        items.append(BomItem(line.ref, line.part, qty, qty * line.unit_cost_usd))
    return items, sum(i.line_cost_usd for i in items)


def _design_rules(spec: DeviceSpec, v: DetectorVariant, qber: float,
                  skr: float) -> list[tuple[str, str]]:
    r: list[tuple[str, str]] = []
    if spec.gate_rate_hz > v.max_gate_rate_hz:
        r.append((FAIL, f"gate rate {spec.gate_rate_hz/1e9:.2f} GHz exceeds the "
                        f"{v.label} max {v.max_gate_rate_hz/1e9:.2f} GHz"))
    if v.needs_self_differencing and spec.gate_rate_hz >= 1e9:
        r.append((INFO, f"GHz gating requires self-differencing front-end; coax delay "
                        f"= {1e9/spec.gate_rate_hz:.2f} ns (1 gate period) — see docs/03"))
    if spec.n_channels not in (2, 4):
        r.append((WARN, f"n_channels={spec.n_channels}: BB84 expects 2 (one-way) or 4 (full)"))
    if qber > 0.11:
        r.append((FAIL, f"QBER {qber*100:.1f}% exceeds the ~11% BB84 security threshold"))
    if skr <= 0.0:
        r.append((FAIL, "no positive secret-key rate at this loss/block size"))
    elif skr < 1e3 and not v.needs_cryostat:
        r.append((WARN, f"low SKR ({skr:.0f} bps) — consider the SNSPD variant for reach"))
    if v.key == "ingaas_sd" and spec.distance_km > 80:
        r.append((WARN, f"{spec.distance_km:.0f} km is long for InGaAs metro; SNSPD reaches further"))
    if v.needs_cryostat:
        r.append((INFO, "SNSPD needs a closed-cycle cryostat (telco data-centre OK) + pol. control"))
    if not any(level == FAIL for level, _ in r):
        r.append((PASS, "all hard constraints satisfied"))
    return r


def configure(spec: DeviceSpec) -> ConfigReport:
    if spec.detector not in DETECTORS:
        raise KeyError(f"unknown detector {spec.detector!r}; have {sorted(DETECTORS)}")
    v = DETECTORS[spec.detector]
    loss = spec.fiber_alpha_db_km * spec.distance_km + spec.bob_insertion_db
    qber, skr, mu1, mu2 = _simulate(spec, v)
    bom, total = _assemble_bom(spec, v)
    rules = _design_rules(spec, v, qber, skr)
    return ConfigReport(
        spec=spec, variant_label=v.label, loss_db=loss, qber=qber, skr_bps=skr,
        mu1=mu1, mu2=mu2, bom=bom, bom_total_usd=total,
        board_params=derive_board_params(spec, v), rules=rules,
        feasible=not any(level == FAIL for level, _ in rules),
    )
