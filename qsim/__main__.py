"""`python -m qsim` — the 1-minute on-ramp to the virtual quantum bench.

Two commands, no configuration:

    python -m qsim              # 4-domain self-check: prove the bench runs (≈1 s)
    python -m qsim gui          # launch the web bench at http://127.0.0.1:8000

The self-check configures one example device in each of the four domains (the same defaults the
GUI loads) and prints a dashboard: headline physics + BOM cost + feasibility. It is the fastest
way for an outsider — investor, telco engineer, student — to confirm the platform works end to
end before reading a line of the deep docs.
"""
from __future__ import annotations

import sys

from . import __version__
from .configurator import configure, domain_schema, list_domains

# what each domain's physics is validated against (the credibility line of the pitch)
_VALIDATION = {
    "qkd": "Rusca et al. 2018 finite-key SKR figure",
    "sensing": "Budker–Romalis projection-noise limit",
    "qchw": "randomized benchmarking error-per-Clifford",
    "qrng": "Monte-Carlo beam-splitter reference",
}

# short labels so the headline reads "QBER 1.05 % · SKR 7.90 Mbps" (full Metric.labels are long)
_ABBREV = {
    "qber": "QBER", "skr_bps": "SKR", "sensitivity_asd": "sensitivity",
    "projection_limit_asd": "SQL", "gate_fidelity": "fidelity", "error_per_gate": "err/gate",
    "min_entropy": "H_min", "extractable_rate": "rate",
}


def _headline(rep) -> str:
    """First two featured metrics with short labels, e.g. 'QBER 1.05 % · SKR 7.90 Mbps'."""
    keys = rep.headline_keys or [m.key for m in rep.metrics]
    shown = []
    for k in keys[:2]:
        m = next(m for m in rep.metrics if m.key == k)
        shown.append(f"{_ABBREV.get(k, m.label)} {m.shown()}")
    return " · ".join(shown)


def check() -> int:
    print(f"\n  qsim · virtual quantum bench   v{__version__}")
    print(f"  one kernel → four quantum devices, each validated against a known result\n")
    header = f"  {'DOMAIN':<34}{'HEADLINE':<40}{'BOM':>8}   STATUS"
    print(header)
    print("  " + "─" * (len(header) - 2))
    all_ok = True
    for d in list_domains():
        rep = configure(d["name"], domain_schema(d["name"])["defaults"])
        all_ok &= rep.feasible
        cost = f"${rep.bom_total_usd/1e3:,.0f}k"
        status = "✓ feasible" if rep.feasible else "✗ INFEASIBLE"
        print(f"  {d['label']:<34}{_headline(rep):<40}{cost:>8}   {status}")
    print("\n  Each device's physics is validated against an independent reference:")
    for d in list_domains():
        print(f"    {d['name']:<9}— {_VALIDATION.get(d['name'], 'see docs/')}")
    print("\n  Next:  python -m qsim gui      → turn the knobs in your browser")
    print("         python -m pytest -q     → run the validation suite\n")
    return 0 if all_ok else 1


def gui(argv: list[str]) -> int:
    port = 8000
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
    try:
        from gui.server import app
    except ImportError:
        print("The GUI needs Flask. Install it with:  pip install -e '.[gui]'", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{port}"
    print(f"\n  qsim virtual bench → {url}   (Ctrl-C to stop)\n")
    try:
        import threading
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    except Exception:
        pass
    app.run(host="127.0.0.1", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "check"
    if cmd in ("check", ""):
        return check()
    if cmd == "gui":
        return gui(argv[1:])
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    print(f"unknown command {cmd!r}. Try:  python -m qsim [check|gui]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
