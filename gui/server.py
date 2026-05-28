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

def _sweep_data(domain: str, knobs: dict):
    """Sweep the domain's chosen knob → arrays for the live chart (+ the current report)."""
    sw = sweep_of(domain)
    rep = configure(domain, knobs)
    xs, ys = [], []
    for v in sw["values"]:
        r = configure(domain, {**knobs, sw["knob"]: v})
        ok = r.feasible and r.m(sw["metric"]) > 0
        xs.append(v)
        ys.append(r.m(sw["metric"]) if ok else None)
    cur_x = float(knobs.get(sw["knob"], xs[len(xs) // 2]))
    cur_ok = rep.feasible and rep.m(sw["metric"]) > 0
    data = {"knob": sw["knob"], "label": sw["label"], "metric": sw["metric"],
            "metric_label": sw["metric_label"], "logy": bool(sw.get("logy")),
            "logx": bool(sw.get("logx")), "x": xs, "y": ys,
            "current_x": cur_x, "current_y": (rep.m(sw["metric"]) if cur_ok else None)}
    return data, rep


def _figure_b64_from(data: dict) -> str:
    """Small PNG of the sweep (kept for API compatibility / non-JS fallback)."""
    xs = np.array(data["x"], float)
    ys = np.array([np.nan if v is None else v for v in data["y"]], float)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    m = np.isfinite(ys)
    plot = ax.semilogy if data["logy"] else ax.plot
    plot(xs[m], ys[m], "-", color="#22a7c0", lw=2)
    if data["current_y"] is not None:
        ax.plot([data["current_x"]], [data["current_y"]], "o", color="#c0392b", ms=9)
    ax.set_xlabel(data["label"])
    ax.set_ylabel(data["metric_label"])
    ax.set_title(f"{data['metric_label']} vs {data['label']}")
    ax.grid(alpha=0.25, which="both")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
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
        sweep, rep = _sweep_data(domain, knobs)
        out = rep.to_dict()
        out["sweep"] = sweep
        out["figure_b64"] = _figure_b64_from(sweep)
        return jsonify(out)
    except Exception as e:  # surface bad combos as a message, not a 500
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
