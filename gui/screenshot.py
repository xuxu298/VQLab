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
    outdir = os.path.dirname(OUT)
    os.makedirs(outdir, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 950})
        page.goto(URL, wait_until="networkidle")
        domains = page.eval_on_selector_all("#domain option", "els => els.map(e => e.value)")
        prev_fig = ""
        for i, dom in enumerate(domains):
            page.select_option("#domain", dom)
            if i == 0:
                # initial load already rendered qkd; just ensure the figure is present
                page.wait_for_function("document.getElementById('fig').src.length > 100",
                                       timeout=20000)
            else:
                # switching domains regenerates the figure — wait until its src changes
                page.wait_for_function("s => document.getElementById('fig').src !== s",
                                       arg=prev_fig, timeout=25000)
            page.wait_for_timeout(700)
            prev_fig = page.get_attribute("#fig", "src")
            out = OUT if i == 0 else os.path.join(outdir, f"g1_gui_{dom}.png")
            page.screenshot(path=os.path.abspath(out), full_page=True)
            print(f"[C3] wrote {os.path.abspath(out)}  ({dom})")
        browser.close()


if __name__ == "__main__":
    main()
