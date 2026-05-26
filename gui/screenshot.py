"""Render the running GUI to a PNG with headless Chromium (verification / docs).

Assumes the server is running at http://127.0.0.1:8000 (python -m gui.server).
Run:  python -m gui.screenshot
"""
from __future__ import annotations

import os

from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), "..", "demos", "figures", "g1_gui.png")
URL = os.environ.get("GUI_URL", "http://127.0.0.1:8000")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL, wait_until="networkidle")
        # wait for the first /api/configure round-trip to populate the metrics
        page.wait_for_function("document.getElementById('m_skr').textContent !== '–'",
                               timeout=15000)
        page.wait_for_timeout(400)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        page.screenshot(path=os.path.abspath(OUT), full_page=True)
        browser.close()
    print(f"[G1] wrote {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
