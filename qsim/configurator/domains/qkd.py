"""QKD domain — a full decoy-BB84 Alice→fiber→Bob link, on the generic configurator.

Wraps the validated qsim QKD finite-key model + the variant catalog into the domain-agnostic
ConfigReport. (This is the former standalone configurator, now one domain among several.)
"""
from __future__ import annotations

from ...qkd.channel import ChannelParams, gain_qber
from ...qkd.keyrate import optimize_skr, skr_for_params
from ..catalog import (ALICE_COMMON_BOM, BOB_COMMON_BOM, DETECTORS, ENCODER_BOM, LINK_BOM,
                       QRNGS, SOURCES, catalog_options, derive_board_params)
from ..registry import Domain, register_domain
from ..report import FAIL, INFO, PASS, WARN, ConfigReport, Metric, assemble_bom, feasible
from ..spec import DeviceSpec

_OPT = catalog_options()

SCHEMA = [
    {"key": "detector", "label": "Detector (Bob)", "type": "select", "options": _OPT["detector"]},
    {"key": "source", "label": "Laser source (Alice)", "type": "select", "options": _OPT["source"]},
    {"key": "qrng", "label": "QRNG (Alice)", "type": "select", "options": _OPT["qrng"]},
    {"key": "n_channels", "label": "Detector channels", "type": "select",
     "options": [{"key": 2, "label": "2 (one-way)"}, {"key": 4, "label": "4 (full)"}]},
    {"key": "distance_km", "label": "Distance", "type": "range", "min": 1, "max": 120,
     "step": 1, "unit": "km"},
    {"key": "gate_rate_ghz", "label": "Gate rate", "type": "range", "min": 0.1, "max": 2.5,
     "step": 0.05, "unit": "GHz"},
    {"key": "modulator_er_db", "label": "Modulator extinction ratio", "type": "range",
     "min": 10, "max": 40, "step": 1, "unit": "dB"},
    {"key": "amzi_visibility", "label": "Bob AMZI visibility", "type": "number",
     "min": 0.8, "max": 1.0, "step": 0.005},
]
DEFAULTS = {"detector": "ingaas_sd", "source": "gainswitched_dfb", "qrng": "quantis",
            "n_channels": 2, "distance_km": 25, "gate_rate_ghz": 1.25,
            "modulator_er_db": 30, "amzi_visibility": 0.98}
SWEEP = {"knob": "distance_km", "label": "distance (km)", "metric": "skr_bps",
         "metric_label": "secret-key rate (bps)", "values": list(range(1, 121, 3)), "logy": True}


def _spec(knobs: dict) -> DeviceSpec:
    k = dict(knobs)
    if "gate_rate_ghz" in k:
        k["gate_rate_hz"] = float(k.pop("gate_rate_ghz")) * 1e9
    k.setdefault("name", "qkd_link")
    fields = set(DeviceSpec.__dataclass_fields__)
    return DeviceSpec(**{f: v for f, v in k.items() if f in fields})


def _intrinsic_error(spec: DeviceSpec) -> float:
    if spec.e_misalignment is not None:
        return spec.e_misalignment
    e_amzi = (1.0 - spec.amzi_visibility) / 2.0
    e_enc = 1.0 / (2.0 * 10.0 ** (spec.modulator_er_db / 10.0))
    return e_amzi + e_enc


def configure(knobs: dict) -> ConfigReport:
    spec = _spec(knobs)
    det, src = DETECTORS[spec.detector], SOURCES[spec.source]
    e_d = _intrinsic_error(spec)
    loss = spec.fiber_alpha_db_km * spec.distance_km + spec.bob_insertion_db
    params = ChannelParams(eta_det=det.eta, fiber_alpha=spec.fiber_alpha_db_km,
                           p_dc=det.p_dark_per_gate, e_d=e_d, tau_dead=det.tau_dead)
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

    bom_lines = (list(SOURCES[spec.source].bom) + ENCODER_BOM[spec.encoder]
                 + QRNGS[spec.qrng].bom + ALICE_COMMON_BOM + list(det.bom)
                 + BOB_COMMON_BOM + LINK_BOM)
    bom, by_side, total = assemble_bom(bom_lines, n_channels=spec.n_channels)
    board = derive_board_params(spec, det)
    rules = _rules(spec, det, src, qber, skr, board)

    skr_disp = (f"{skr/1e6:.2f} Mbps" if skr >= 1e5 else
                (f"{skr/1e3:.1f} kbps" if skr >= 1e3 else f"{skr:.0f} bps"))
    metrics = [
        Metric("qber", "QBER", qber * 100, "%", f"{qber*100:.2f} %"),
        Metric("skr_bps", "Secret-key rate", skr, "bps", skr_disp),
        Metric("link_cost", "Whole-link BOM", total, "USD", f"${total/1e3:,.0f}k"),
        Metric("loss_db", "Link loss", loss, "dB", f"{loss:.1f} dB"),
        Metric("e_d", "Intrinsic error", e_d * 100, "%", f"{e_d*100:.2f} %"),
    ]
    return ConfigReport(domain="qkd", name=spec.name, metrics=metrics, bom=bom,
                        cost_by_side=by_side, bom_total_usd=total, board_params=board,
                        rules=rules, feasible=feasible(rules),
                        headline_keys=["qber", "skr_bps", "link_cost", "loss_db"])


def _rules(spec, det, src, qber, skr, board):
    r = []
    if spec.gate_rate_hz > det.max_gate_rate_hz:
        r.append((FAIL, f"gate rate {spec.gate_rate_hz/1e9:.2f} GHz exceeds {det.label} max "
                        f"{det.max_gate_rate_hz/1e9:.2f} GHz"))
    if spec.gate_rate_hz > src.max_rep_rate_hz:
        r.append((FAIL, f"rep rate {spec.gate_rate_hz/1e9:.2f} GHz exceeds {src.label} max "
                        f"{src.max_rep_rate_hz/1e9:.2f} GHz"))
    if det.needs_self_differencing and spec.gate_rate_hz >= 1e9:
        r.append((INFO, f"GHz gating requires self-differencing; coax delay "
                        f"= {board['sd_delay_line_ns']} ns (1 gate period) — docs/03"))
    if spec.modulator_er_db < 20:
        r.append((FAIL, f"modulator ER {spec.modulator_er_db:.0f} dB too low — state-prep "
                        f"error/security compromised (need >~25-30 dB)"))
    elif spec.modulator_er_db < 25:
        r.append((WARN, f"modulator ER {spec.modulator_er_db:.0f} dB marginal; aim >30 dB"))
    if board["total_jitter_ps"] > 0.25 * board["gate_period_ps"]:
        r.append((WARN, f"total jitter {board['total_jitter_ps']} ps > 25% of the "
                        f"{board['gate_period_ps']} ps gate period — timing/ISI risk"))
    r.append((INFO, "Alice A3 encoder ΔL must be matched to Bob B2 AMZI ΔL"))
    if spec.n_channels not in (2, 4):
        r.append((WARN, f"n_channels={spec.n_channels}: BB84 expects 2 or 4"))
    if qber > 0.11:
        r.append((FAIL, f"QBER {qber*100:.1f}% exceeds the ~11% BB84 security threshold"))
    if skr <= 0.0:
        r.append((FAIL, "no positive secret-key rate at this loss/block size"))
    elif skr < 1e3 and not det.needs_cryostat:
        r.append((WARN, f"low SKR ({skr:.0f} bps) — consider the SNSPD variant for reach"))
    if det.key == "ingaas_sd" and spec.distance_km > 80:
        r.append((WARN, f"{spec.distance_km:.0f} km long for InGaAs; SNSPD reaches further"))
    if det.needs_cryostat:
        r.append((INFO, "SNSPD needs a closed-cycle cryostat (telco DC OK) + pol. control"))
    if feasible(r):
        r.append((PASS, "all hard constraints satisfied"))
    return r


register_domain(Domain(name="qkd", label="QKD link (decoy-BB84)", schema=SCHEMA,
                       defaults=DEFAULTS, configure=configure, sweep=SWEEP))
