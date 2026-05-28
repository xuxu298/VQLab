"""Render the running production GUI to PNGs with headless Chromium (QA / docs / video stills).

Assumes the server is running at http://127.0.0.1:8000 (python -m gui.server).
Run:  python -m gui.screenshot              # all domains, 1920x1080 viewport
"""
from __future__ import annotations

import os

from playwright.sync_api import sync_playwright

OUTDIR = os.path.join(os.path.dirname(__file__), "..", "demos", "figures")
URL = os.environ.get("GUI_URL", "http://127.0.0.1:8000")
W, H = 1920, 1080


def main() -> None:
    os.makedirs(OUTDIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(2600)  # web fonts + ECharts init
        domains = page.eval_on_selector_all(".domtab", "els => els.map(e => e.dataset.d)")
        for i, dom in enumerate(domains):
            page.click(f'.domtab[data-d="{dom}"]')
            page.wait_for_function("!document.getElementById('busy').classList.contains('on')",
                                   timeout=30000)
            page.wait_for_function("document.querySelectorAll('#metrics .metric').length > 0",
                                   timeout=30000)
            page.wait_for_timeout(900)  # settle chart animation
            out = os.path.join(OUTDIR, f"gui_{dom}.png")
            page.screenshot(path=os.path.abspath(out))
            print(f"wrote {os.path.abspath(out)}  ({dom})")
        browser.close()


if __name__ == "__main__":
    main()
