"""Compile a DeviceSpec into a unified configuration: behavioural sim + hardware + rules.

`configure(spec)` realises the configurator across the full Alice→fiber→Bob link: from the
high-level knobs it (1) runs qsim's validated finite-key model for QBER/SKR (with the intrinsic
error derived from the Alice modulator extinction ratio and the Bob AMZI visibility), (2)
assembles the whole-link BOM (Alice + Bob + shared) with a per-side cost split, and (3) runs
design-rule checks tying the two together. Change one knob -> all of it updates consistently.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..qkd.channel import ChannelParams, gain_qber
from ..qkd.keyrate import optimize_skr, skr_for_params
from .catalog import (ALICE, ALICE_COMMON_BOM, BOB, BOB_COMMON_BOM, DETECTORS, ENCODER_BOM,
                      LINK_BOM, QRNGS, SHARED, SOURCES, DetectorVariant, derive_board_params)
from .spec import DeviceSpec

PASS, INFO, WARN, FAIL = "PASS", "INFO", "WARN", "FAIL"


@dataclass
class BomItem:
    ref: str
    part: str
    side: str
    qty: int
    line_cost_usd: float


@dataclass
class ConfigReport:
    spec: DeviceSpec
    variant_label: str
    source_label: str
    loss_db: float
    e_d: float
    qber: float
    skr_bps: float
    mu1: float
    mu2: float
    bom: list[BomItem]
    cost_by_side: dict
    bom_total_usd: float
    board_params: dict
    rules: list[tuple[str, str]]
    feasible: bool

    def to_dict(self) -> dict:
        """JSON-serialisable form (for the GUI / API)."""
        return {
            "name": self.spec.name,
            "source_label": self.source_label,
            "variant_label": self.variant_label,
            "loss_db": self.loss_db,
            "e_d": self.e_d,
            "qber": self.qber,
            "skr_bps": self.skr_bps,
            "mu1": self.mu1,
            "mu2": self.mu2,
            "bom": [{"ref": it.ref, "part": it.part, "side": it.side,
                     "qty": it.qty, "line_cost_usd": it.line_cost_usd} for it in self.bom],
            "cost_by_side": self.cost_by_side,
            "bom_total_usd": self.bom_total_usd,
            "board_params": {k: str(v) for k, v in self.board_params.items()},
            "rules": [{"level": lv, "msg": m} for lv, m in self.rules],
            "feasible": self.feasible,
        }

    def format(self) -> str:
        s = self.spec
        L = [
            f"=== configured QKD link: {s.name} ===",
            f"  Alice : {self.source_label}, {s.encoder}, ER {s.modulator_er_db:.0f} dB, "
            f"QRNG {s.qrng}",
            f"  fiber : {s.distance_km:.0f} km @ {s.fiber_alpha_db_km} dB/km  ->  link loss "
            f"{self.loss_db:.1f} dB",
            f"  Bob   : {self.variant_label}, {s.n_channels} ch @ {s.gate_rate_hz/1e9:.2f} GHz",
            "",
            "  -- behavioural sim (qsim finite-key) --",
            f"    intrinsic error : {self.e_d*100:.2f} %  (Alice modulator + Bob AMZI)",
            f"    QBER            : {self.qber*100:.2f} %",
            f"    secret-key rate : {self.skr_bps:,.0f} bps"
            + (f" ({self.skr_bps/1e6:.2f} Mbps)" if self.skr_bps >= 1e5 else ""),
            f"    optimal mu1/mu2 : {self.mu1:.3f} / {self.mu2:.3f}",
            "",
            "  -- derived board parameters --",
        ]
        for k, v in self.board_params.items():
            L.append(f"    {k:<24}: {v}")
        L += ["", "  -- bill of materials (whole link) --"]
        for side in (ALICE, SHARED, BOB):
            items = [it for it in self.bom if it.side == side]
            if not items:
                continue
            L.append(f"   [{side}]")
            for it in items:
                L.append(f"    {it.ref:<5} x{it.qty:<2} {it.part:<52} ${it.line_cost_usd:,.0f}")
            L.append(f"    {'':<5}    {side+' subtotal':<52} ${self.cost_by_side[side]:,.0f}")
        L.append(f"    {'':<5}    {'LINK TOTAL':<52} ${self.bom_total_usd:,.0f}")
        L += ["", "  -- design rules --"]
        for level, msg in self.rules:
            L.append(f"    [{level}] {msg}")
        L.append(f"  => {'FEASIBLE' if self.feasible else 'NOT FEASIBLE'}")
        return "\n".join(L)


def _intrinsic_error(spec: DeviceSpec) -> float:
    """Total intrinsic optical error e_d from Alice (modulator ER) + Bob (AMZI visibility).

    e_amzi = (1-V)/2 (interference visibility); e_enc = 1/(2*r_ext) is a behavioral
    state-preparation-error floor from a finite intensity-modulator extinction ratio
    r_ext = 10^(ER_dB/10). Override with spec.e_misalignment if set."""
    if spec.e_misalignment is not None:
        return spec.e_misalignment
    e_amzi = (1.0 - spec.amzi_visibility) / 2.0
    r_ext = 10.0 ** (spec.modulator_er_db / 10.0)
    e_enc = 1.0 / (2.0 * r_ext)
    return e_amzi + e_enc


def _channel_params(spec: DeviceSpec, det: DetectorVariant, e_d: float) -> ChannelParams:
    return ChannelParams(eta_det=det.eta, fiber_alpha=spec.fiber_alpha_db_km,
                         p_dc=det.p_dark_per_gate, e_d=e_d, tau_dead=det.tau_dead)


def _simulate(spec: DeviceSpec, det: DetectorVariant, e_d: float):
    loss = spec.fiber_alpha_db_km * spec.distance_km + spec.bob_insertion_db
    params = _channel_params(spec, det, e_d)
    if spec.mu1 is not None and spec.mu2 is not None:
        skr, _ = skr_for_params(loss, spec.n_z_block, spec.mu1, spec.mu2, 0.7, 0.9,
                                rep_rate=spec.gate_rate_hz, params=params,
                                eps_sec=1e-9, eps_cor=1e-15, f_ec=1.16)
        mu1, mu2 = spec.mu1, spec.mu2
    else:
        pt = optimize_skr(loss, spec.n_z_block, rep_rate=spec.gate_rate_hz, params=params,
                          f_ec=1.16, eps_sec=1e-9, eps_cor=1e-15, n_restarts=6)
        skr, mu1, mu2 = pt.skr, pt.mu1, pt.mu2
    eta = det.eta * 10.0 ** (-loss / 10.0)
    _, qber = gain_qber(mu1, eta, det.p_dark_per_gate, e_d)
    return loss, qber, skr, mu1, mu2


def _assemble_bom(spec: DeviceSpec, det: DetectorVariant):
    lines = (list(SOURCES[spec.source].bom) + ENCODER_BOM[spec.encoder]
             + QRNGS[spec.qrng].bom + ALICE_COMMON_BOM
             + list(det.bom) + BOB_COMMON_BOM + LINK_BOM)
    items: list[BomItem] = []
    for ln in lines:
        qty = ln.qty_per_channel * spec.n_channels + ln.qty_per_board
        if qty == 0:
            continue
        items.append(BomItem(ln.ref, ln.part, ln.side, qty, qty * ln.unit_cost_usd))
    by_side = {ALICE: 0.0, SHARED: 0.0, BOB: 0.0}
    for it in items:
        by_side[it.side] += it.line_cost_usd
    return items, by_side, sum(by_side.values())


def _design_rules(spec, det, src, qber, skr, board) -> list[tuple[str, str]]:
    r: list[tuple[str, str]] = []
    # gating / source rate limits
    if spec.gate_rate_hz > det.max_gate_rate_hz:
        r.append((FAIL, f"gate rate {spec.gate_rate_hz/1e9:.2f} GHz exceeds {det.label} max "
                        f"{det.max_gate_rate_hz/1e9:.2f} GHz"))
    if spec.gate_rate_hz > src.max_rep_rate_hz:
        r.append((FAIL, f"rep rate {spec.gate_rate_hz/1e9:.2f} GHz exceeds {src.label} max "
                        f"{src.max_rep_rate_hz/1e9:.2f} GHz"))
    if det.needs_self_differencing and spec.gate_rate_hz >= 1e9:
        r.append((INFO, f"GHz gating requires self-differencing; coax delay "
                        f"= {board['sd_delay_line_ns']} ns (1 gate period) — docs/03"))
    # security: modulator extinction ratio
    if spec.modulator_er_db < 20:
        r.append((FAIL, f"modulator ER {spec.modulator_er_db:.0f} dB too low — state-prep "
                        f"error/security compromised (need >~25-30 dB)"))
    elif spec.modulator_er_db < 25:
        r.append((WARN, f"modulator ER {spec.modulator_er_db:.0f} dB marginal; aim >30 dB"))
    # timing budget: total jitter vs gate period
    if board["total_jitter_ps"] > 0.25 * board["gate_period_ps"]:
        r.append((WARN, f"total jitter {board['total_jitter_ps']} ps > 25% of the "
                        f"{board['gate_period_ps']} ps gate period — timing/ISI risk; "
                        f"lower the rate or pick a lower-jitter detector"))
    # structural / sim
    r.append((INFO, "Alice A3 encoder ΔL must be matched to Bob B2 AMZI ΔL (interferometer pair)"))
    if QRNGS[spec.qrng].min_entropy < 0.95:
        r.append((WARN, f"QRNG min-entropy {QRNGS[spec.qrng].min_entropy} low; needs extraction"))
    if spec.n_channels not in (2, 4):
        r.append((WARN, f"n_channels={spec.n_channels}: BB84 expects 2 (one-way) or 4 (full)"))
    if qber > 0.11:
        r.append((FAIL, f"QBER {qber*100:.1f}% exceeds the ~11% BB84 security threshold"))
    if skr <= 0.0:
        r.append((FAIL, "no positive secret-key rate at this loss/block size"))
    elif skr < 1e3 and not det.needs_cryostat:
        r.append((WARN, f"low SKR ({skr:.0f} bps) — consider the SNSPD variant for reach"))
    if det.key == "ingaas_sd" and spec.distance_km > 80:
        r.append((WARN, f"{spec.distance_km:.0f} km is long for InGaAs metro; SNSPD reaches further"))
    if det.needs_cryostat:
        r.append((INFO, "SNSPD needs a closed-cycle cryostat (telco data-centre OK) + pol. control"))
    if not any(level == FAIL for level, _ in r):
        r.append((PASS, "all hard constraints satisfied"))
    return r


def configure(spec: DeviceSpec) -> ConfigReport:
    for field_name, table in (("detector", DETECTORS), ("source", SOURCES),
                              ("qrng", QRNGS), ("encoder", ENCODER_BOM)):
        key = getattr(spec, field_name)
        if key not in table:
            raise KeyError(f"unknown {field_name} {key!r}; have {sorted(table)}")
    det, src = DETECTORS[spec.detector], SOURCES[spec.source]
    e_d = _intrinsic_error(spec)
    loss, qber, skr, mu1, mu2 = _simulate(spec, det, e_d)
    bom, by_side, total = _assemble_bom(spec, det)
    board = derive_board_params(spec, det)
    rules = _design_rules(spec, det, src, qber, skr, board)
    return ConfigReport(
        spec=spec, variant_label=det.label, source_label=src.label, loss_db=loss,
        e_d=e_d, qber=qber, skr_bps=skr, mu1=mu1, mu2=mu2,
        bom=bom, cost_by_side=by_side, bom_total_usd=total, board_params=board,
        rules=rules, feasible=not any(level == FAIL for level, _ in rules),
    )
