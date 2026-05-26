"""Flask backend for the qsim virtual-bench GUI — a thin layer over configure().

Endpoints:
  GET  /              -> the single-page UI (gui/index.html)
  GET  /api/catalog   -> variant options + the default DeviceSpec (for the form)
  POST /api/configure -> {DeviceSpec knobs} -> {ConfigReport JSON + SKR/cost figure (base64)}

The engine stays server-side (mission: browser, no install, modest client hardware); the front
end is static vanilla JS. Run:  python -m gui.server  then open http://127.0.0.1:8000
"""
from __future__ import annotations

import base64
import io
import os
from dataclasses import asdict

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

from qsim.configurator import DeviceSpec, configure  # noqa: E402
from qsim.configurator.catalog import catalog_options  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

SIDE_COLS = {"Alice": "#7fb3d5", "shared": "#aab7b8", "Bob": "#e59866"}


def _figure_b64(spec: DeviceSpec) -> str:
    """SKR-vs-distance (current detector, operating point marked) + cost-by-side bar."""
    rep = configure(spec)
    dists = np.linspace(1, max(60, spec.distance_km * 1.6), 36)
    skr = []
    for d in dists:
        r = configure(spec.replace(distance_km=float(d)))
        skr.append(r.skr_bps if (r.feasible and r.skr_bps > 0) else np.nan)
    skr = np.array(skr)

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(10, 3.8),
                                   gridspec_kw={"width_ratios": [2, 1]})
    m = np.isfinite(skr)
    axA.semilogy(dists[m], skr[m], "-", color="#2471a3", lw=2)
    if rep.feasible and rep.skr_bps > 0:
        axA.plot([spec.distance_km], [rep.skr_bps], "o", color="#c0392b", ms=9)
    axA.set_xlabel("distance (km)")
    axA.set_ylabel("secret-key rate (bps)")
    axA.set_title("SKR vs distance")
    axA.grid(alpha=0.25, which="both")

    bottom = 0.0
    for side in ("Alice", "shared", "Bob"):
        v = rep.cost_by_side.get(side, 0.0) / 1e3
        axB.bar(["link"], [v], bottom=[bottom], color=SIDE_COLS[side], label=side)
        bottom += v
    axB.set_ylabel("BOM cost (k USD)")
    axB.set_title(f"whole-link BOM = ${rep.bom_total_usd/1e3:,.0f}k")
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


@app.get("/api/catalog")
def api_catalog():
    return jsonify({"options": catalog_options(), "default": asdict(DeviceSpec())})


@app.post("/api/configure")
def api_configure():
    data = request.get_json(force=True) or {}
    fields = set(DeviceSpec.__dataclass_fields__)
    kw = {k: v for k, v in data.items() if k in fields}
    for f in DeviceSpec._FLOAT_FIELDS:
        if kw.get(f) not in (None, ""):
            kw[f] = float(kw[f])
        elif f in kw:
            kw[f] = None
    if "n_channels" in kw:
        kw["n_channels"] = int(kw["n_channels"])
    try:
        rep = configure(DeviceSpec(**kw))
    except Exception as e:  # surface bad combos as a message, not a 500
        return jsonify({"error": str(e)}), 400
    out = rep.to_dict()
    out["figure_b64"] = _figure_b64(rep.spec)
    return jsonify(out)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
