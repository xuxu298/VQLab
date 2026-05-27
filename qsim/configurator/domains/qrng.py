"""QRNG domain — a beam-splitter quantum random-number generator, on the generic configurator.

The fourth domain. It reuses the SAME physics as the qsim QRNG plugin (`qsim/qrng/`): a faint
pulse hits a 50/50 beam splitter and two threshold detectors A/B; the raw bit is which detector
clicked. The randomness is only as good as the device — detector efficiency mismatch and
dark-count asymmetry bias the bit and lower the extractable min-entropy.

Like sensing/qchw this domain evaluates a CLOSED-FORM model (no Monte-Carlo, so the GUI is
instant). The closed form is the *expectation* of the plugin's batched model, so it is validated
against the MC `run_qrng` in tests/test_configurator.py (the project's two-tier discipline):

  per-arm click prob:  pa = 1 - exp(-eta_a * mu/2) * (1 - p_dc_a)     (Fock backend + dark)
  kept single-clicks:  P(bit0)=pa(1-pb),  P(bit1)=pb(1-pa)            (clicks independent)
  bias = |P(1|kept) - 1/2|,  H_min = -log2 max(p0,p1)                 (extractable per raw bit)
"""
from __future__ import annotations

import math

from ..catalog import BomLine
from ..registry import Domain, register_domain
from ..report import FAIL, INFO, PASS, WARN, ConfigReport, Metric, assemble_bom, feasible

_DARK_OPTS = [{"key": v, "label": f"{v:.0e}"} for v in (1e-7, 1e-6, 1e-5, 1e-4, 1e-3)]
_REP_OPTS = [{"key": 1e7, "label": "10 MHz"}, {"key": 1e8, "label": "100 MHz"},
             {"key": 1e9, "label": "1 GHz"}, {"key": 2.5e9, "label": "2.5 GHz"}]

SCHEMA = [
    {"key": "mu", "label": "Mean photon number μ", "type": "range",
     "min": 0.05, "max": 2.0, "step": 0.05, "unit": ""},
    {"key": "rep_rate", "label": "Source rep-rate", "type": "select", "options": _REP_OPTS},
    {"key": "eta_a", "label": "Detector A efficiency", "type": "range",
     "min": 0.05, "max": 0.95, "step": 0.01, "unit": ""},
    {"key": "eta_b", "label": "Detector B efficiency", "type": "range",
     "min": 0.05, "max": 0.95, "step": 0.01, "unit": ""},
    {"key": "p_dark_a", "label": "Detector A dark prob", "type": "select", "options": _DARK_OPTS},
    {"key": "p_dark_b", "label": "Detector B dark prob", "type": "select", "options": _DARK_OPTS},
]
DEFAULTS = {"mu": 0.5, "rep_rate": 1e8, "eta_a": 0.20, "eta_b": 0.20,
            "p_dark_a": 1e-5, "p_dark_b": 1e-5}
SWEEP = {"knob": "eta_b", "label": "detector B efficiency η_b", "metric": "min_entropy",
         "metric_label": "min-entropy (bits/bit)", "logy": False,
         "values": [round(0.05 + 0.05 * i, 2) for i in range(19)]}   # 0.05 .. 0.95


def _rate(bps: float) -> str:
    if bps >= 1e6:
        return f"{bps/1e6:.2f} Mbps"
    if bps >= 1e3:
        return f"{bps/1e3:.1f} kbps"
    return f"{bps:.0f} bps"


def _click_prob(eta: float, half_mu: float, p_dc: float) -> float:
    p_sig = 1.0 - math.exp(-eta * half_mu)            # Fock backend (qsim/core/backends.py)
    return 1.0 - (1.0 - p_sig) * (1.0 - p_dc)


def configure(knobs: dict) -> ConfigReport:
    mu = float(knobs.get("mu", DEFAULTS["mu"]))
    rep = float(knobs.get("rep_rate", DEFAULTS["rep_rate"]))
    eta_a = float(knobs.get("eta_a", DEFAULTS["eta_a"]))
    eta_b = float(knobs.get("eta_b", DEFAULTS["eta_b"]))
    pda = float(knobs.get("p_dark_a", DEFAULTS["p_dark_a"]))
    pdb = float(knobs.get("p_dark_b", DEFAULTS["p_dark_b"]))

    half = 0.5 * mu                                   # 50/50 split
    pa = _click_prob(eta_a, half, pda)
    pb = _click_prob(eta_b, half, pdb)
    p0 = pa * (1.0 - pb)                              # A clicks alone -> bit 0
    p1 = pb * (1.0 - pa)                              # B clicks alone -> bit 1
    p_double = pa * pb
    sift = p0 + p1
    prob1 = p1 / sift if sift > 0 else 0.5
    bias = abs(prob1 - 0.5)
    pmax = max(prob1, 1.0 - prob1)
    h_min = -math.log2(pmax) if pmax > 0 else 0.0

    raw_rate = rep * sift                             # kept single-click bits/s
    extractable = raw_rate * h_min                    # full-entropy bits/s after a tight extractor
    eta_mean = 0.5 * (eta_a + eta_b)
    mu_opt = 2.0 * math.log(2.0) / eta_mean if eta_mean > 0 else float("nan")

    bom_lines = [
        BomLine("SRC", "faint-pulse source (DFB laser + attenuator) + driver", "optics", qty_per_board=1, unit_cost_usd=1500),
        BomLine("BS",  "50/50 fiber beam-splitter coupler",                    "optics", qty_per_board=1, unit_cost_usd=400),
        BomLine("DET", "single-photon detector module (A & B)",                "optics", qty_per_board=2, unit_cost_usd=2500),
        BomLine("DISC","fast discriminators + coincidence/click logic",        "electronics", qty_per_board=1, unit_cost_usd=900),
        BomLine("FPGA","timestamp + click-routing FPGA",                       "electronics", qty_per_board=1, unit_cost_usd=1200),
        BomLine("EXT", "Toeplitz-hash randomness extractor (FPGA IP)",         "processing", qty_per_board=1, unit_cost_usd=600),
        BomLine("HK",  "enclosure + power + housekeeping",                     "electronics", qty_per_board=1, unit_cost_usd=800),
    ]
    bom, by_side, total = assemble_bom(bom_lines)
    board = {
        "detection_model": "P(click)=1-exp(-η·μ/2) per arm + dark (Fock backend)",
        "optimal_mu": f"{mu_opt:.2f} (maximizes single-click sift @ mean η={eta_mean:.2f})",
        "double_click_frac": f"{p_double:.3g} (discarded)",
        "extractor": "Toeplitz hash sized to H_min -> full-entropy output",
        "output_after_extraction": _rate(extractable),
    }

    rules = []
    if h_min < 0.5:
        rules.append((FAIL, f"min-entropy {h_min:.2f} bit/raw bit too low — detector η or dark "
                            f"asymmetry biases the source past practical extraction"))
    elif h_min < 0.9:
        rules.append((WARN, f"biased source (H_min={h_min:.2f}); a strong Toeplitz extractor is "
                            f"required, output throttled to {_rate(extractable)}"))
    if p_double > sift and sift > 0:
        rules.append((WARN, f"μ={mu:.2f} too high: double-clicks ({p_double:.2g}) exceed usable "
                            f"single-clicks ({sift:.2g}); lower μ toward optimal {mu_opt:.2f}"))
    denom = max(eta_a, eta_b)
    if denom > 0 and abs(eta_a - eta_b) / denom > 0.1:
        rules.append((INFO, f"detector efficiency mismatch (η_a={eta_a:.2f}, η_b={eta_b:.2f}) is "
                            f"the dominant bias source; balance the arms or extract harder"))
    if max(pda, pdb) > (1.0 - math.exp(-eta_mean * half)):
        rules.append((WARN, "dark-count prob exceeds the per-arm signal-click prob — μ too low or "
                            "detectors too noisy; bits are dark-dominated"))
    rules.append((INFO, f"extractable randomness = {_rate(extractable)} "
                        f"(= {_rate(raw_rate)} kept × {h_min:.2f} bit min-entropy)"))
    if feasible(rules):
        rules.append((PASS, "device produces usable quantum randomness"))

    metrics = [
        Metric("min_entropy", "Min-entropy / raw bit", h_min, "bit", f"{h_min:.3f} bit"),
        Metric("extractable_rate", "Extractable rate", extractable, "bps", _rate(extractable)),
        Metric("bias", "Bit bias |P(1)-½|", bias, "", f"{bias:.2e}"),
        Metric("sift_efficiency", "Single-click sift", sift, "", f"{sift*100:.1f} %"),
        Metric("raw_bit_rate", "Raw kept rate", raw_rate, "bps", _rate(raw_rate)),
    ]
    return ConfigReport(domain="qrng", name="beamsplitter_qrng", metrics=metrics, bom=bom,
                        cost_by_side=by_side, bom_total_usd=total, board_params=board,
                        rules=rules, feasible=feasible(rules),
                        headline_keys=["min_entropy", "extractable_rate", "bias", "sift_efficiency"])


register_domain(Domain(name="qrng", label="Quantum RNG (beam-splitter)", schema=SCHEMA,
                       defaults=DEFAULTS, configure=configure, sweep=SWEEP))
