"""Tests for the multi-domain virtual-bench GUI backend (C3) — via the Flask test client.

The live render + reactivity + domain switching are verified separately with Playwright
(gui/screenshot.py); these cover the JSON endpoints the front-end relies on.
"""
from gui.server import app


def client():
    return app.test_client()


def test_domains_endpoint():
    names = {d["name"] for d in client().get("/api/domains").get_json()}
    assert {"qkd", "sensing", "qchw"} <= names


def test_schema_endpoint_per_domain():
    for dom in ("qkd", "sensing", "qchw"):
        s = client().get(f"/api/schema/{dom}").get_json()
        assert s["schema"] and s["defaults"]


def test_schema_unknown_domain_404():
    assert client().get("/api/schema/nope").status_code == 404


def test_configure_each_domain_with_defaults():
    c = client()
    for dom in ("qkd", "sensing", "qchw"):
        defaults = c.get(f"/api/schema/{dom}").get_json()["defaults"]
        r = c.post("/api/configure", json={"domain": dom, "knobs": defaults}).get_json()
        assert r["feasible"] is True
        assert r["metrics"] and r["bom"]
        assert isinstance(r["figure_b64"], str) and len(r["figure_b64"]) > 1000
        assert r["domain"] == dom


def test_configure_bad_knobs_returns_400():
    r = client().post("/api/configure",
                      json={"domain": "qkd", "knobs": {"detector": "nope"}})
    assert r.status_code == 400
    assert "error" in r.get_json()
