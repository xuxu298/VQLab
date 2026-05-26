"""Tests for the virtual-bench GUI backend (G1) — via the Flask test client (no browser).

Checks the catalog and configure endpoints the front-end relies on. The live render +
reactivity are verified separately with Playwright (gui/screenshot.py).
"""
from gui.server import app


def client():
    return app.test_client()


def test_catalog_endpoint():
    r = client().get("/api/catalog").get_json()
    keys = [o["key"] for o in r["options"]["detector"]]
    assert "ingaas_sd" in keys and "snspd" in keys
    assert r["default"]["detector"] == "ingaas_sd"
    assert "source" in r["options"] and "qrng" in r["options"]


def test_configure_endpoint_default_is_feasible():
    r = client().post("/api/configure",
                      json={"detector": "ingaas_sd", "distance_km": 25}).get_json()
    assert r["feasible"] is True
    assert r["skr_bps"] > 0
    assert r["bom_total_usd"] > 0
    assert {"Alice", "Bob"} <= set(r["cost_by_side"])
    assert len(r["bom"]) > 5
    assert isinstance(r["figure_b64"], str) and len(r["figure_b64"]) > 1000


def test_configure_detector_swap_changes_skr_and_cost():
    c = client()
    a = c.post("/api/configure", json={"detector": "ingaas_sd", "distance_km": 25}).get_json()
    b = c.post("/api/configure", json={"detector": "snspd", "distance_km": 25}).get_json()
    assert b["skr_bps"] > a["skr_bps"]
    assert b["bom_total_usd"] > a["bom_total_usd"]


def test_configure_low_extinction_ratio_is_infeasible():
    r = client().post("/api/configure",
                      json={"detector": "ingaas_sd", "modulator_er_db": 15}).get_json()
    assert r["feasible"] is False


def test_configure_unknown_detector_returns_400():
    r = client().post("/api/configure", json={"detector": "nope"})
    assert r.status_code == 400
    assert "error" in r.get_json()
