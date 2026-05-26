"""Flask backend for the qsim virtual-bench GUI — a thin, domain-agnostic layer over the
multi-domain configurator.

Endpoints:
  GET  /                     -> the single-page UI (gui/index.html)
  GET  /api/domains          -> [{name, label}, ...]
  GET  /api/schema/<domain>  -> {schema, defaults} for that domain's knobs
  POST /api/configure        -> {domain, knobs} -> {ConfigReport JSON + swept figure (base64)}

The engine stays server-side (mission: browser, no install, modest client hardware); the front
end is static vanilla JS. Run:  python -m gui.server  then open http://127.0.0.1:8000
"""
from __future__ import annotations

import base64
import io
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

from qsim.configurator import configure, domain_schema, list_domains, sweep_of  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

SIDE_COLS = ["#7fb3d5", "#e59866", "#aab7b8", "#82c9a0", "#c39bd3", "#f0b27a"]


def _figure_b64(domain: str, knobs: dict) -> str:
    """Sweep the domain's chosen knob (metric vs knob) + a cost-by-side bar."""
    sw = sweep_of(domain)
    rep = configure(domain, knobs)
    xs, ys = [], []
    for v in sw["values"]:
        r = configure(domain, {**knobs, sw["knob"]: v})
        xs.append(v)
        ys.append(r.m(sw["metric"]) if (r.feasible and r.m(sw["metric"]) > 0) else np.nan)
    xs, ys = np.array(xs, float), np.array(ys, float)

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(10, 3.8),
                                   gridspec_kw={"width_ratios": [2, 1]})
    m = np.isfinite(ys)
    plot = axA.loglog if (sw.get("logy") and sw.get("logx")) else \
        (axA.semilogy if sw.get("logy") else axA.plot)
    plot(xs[m], ys[m], "-", color="#2471a3", lw=2)
    cur_x = float(knobs.get(sw["knob"], xs[len(xs) // 2]))
    if rep.feasible and rep.m(sw["metric"]) > 0:
        axA.plot([cur_x], [rep.m(sw["metric"])], "o", color="#c0392b", ms=9)
    axA.set_xlabel(sw["label"])
    axA.set_ylabel(sw["metric_label"])
    axA.set_title(f"{sw['metric_label']} vs {sw['label']}")
    axA.grid(alpha=0.25, which="both")

    bottom, sides = 0.0, list(rep.cost_by_side)
    for i, side in enumerate(sides):
        v = rep.cost_by_side[side] / 1e3
        axB.bar(["BOM"], [v], bottom=[bottom], color=SIDE_COLS[i % len(SIDE_COLS)], label=side)
        bottom += v
    axB.set_ylabel("BOM cost (k USD)")
    axB.set_title(f"BOM = ${rep.bom_total_usd/1e3:,.0f}k")
    axB.legend(fontsize=7, loc="upper left")
    axB.grid(alpha=0.25, axis="y")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/api/domains")
def api_domains():
    return jsonify(list_domains())


@app.get("/api/schema/<domain>")
def api_schema(domain):
    try:
        return jsonify(domain_schema(domain))
    except KeyError as e:
        return jsonify({"error": str(e)}), 404


@app.post("/api/configure")
def api_configure():
    data = request.get_json(force=True) or {}
    domain = data.get("domain", "qkd")
    knobs = data.get("knobs", {})
    try:
        rep = configure(domain, knobs)
        out = rep.to_dict()
        out["figure_b64"] = _figure_b64(domain, knobs)
        return jsonify(out)
    except Exception as e:  # surface bad combos as a message, not a 500
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
