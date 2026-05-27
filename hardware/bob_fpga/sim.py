"""Build the Bob FPGA firmware with Verilator and run its self-checking C++ testbench.

`bob_gating.v` is synthesizable RTL; `sim_main.cpp` is a Verilator harness that drives it through
named behavioural scenarios and exits non-zero on any failure. This wrapper invokes Verilator
(the canonical --cc --exe --build flow, works on Verilator >= 4.0) and runs the result.

Run:  python -m hardware.bob_fpga.sim       (or:  python hardware/bob_fpga/sim.py)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "obj_dir", "Vbob_sim")


def have_verilator() -> bool:
    return shutil.which("verilator") is not None


def build() -> subprocess.CompletedProcess:
    cmd = [
        "verilator", "--cc", "--exe", "--build", "-Wall", "-Wno-fatal",
        "--top-module", "bob_gating", "-o", "Vbob_sim",
        "sim_main.cpp", "bob_gating.v",
    ]
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)


def run() -> subprocess.CompletedProcess:
    return subprocess.run([BIN], cwd=HERE, capture_output=True, text=True)


def build_and_run() -> tuple[int, str]:
    """Return (exit_code, combined_output). Non-zero exit = a check failed or the build broke."""
    if not have_verilator():
        return 127, "verilator not found on PATH (apt install verilator)"
    b = build()
    if b.returncode != 0:
        return b.returncode, "verilator build failed:\n" + b.stdout + b.stderr
    r = run()
    return r.returncode, r.stdout + r.stderr


def ensure_built() -> bool:
    """Build the sim if the binary is missing. Returns True if a runnable binary exists."""
    if not have_verilator():
        return False
    if not os.path.exists(BIN):
        if build().returncode != 0:
            return False
    return True


def run_stream(veto: int, pclick: float, gates: int = 1_000_000, seed: int = 1) -> dict:
    """Drive the firmware with a Bernoulli(pclick) comparator stream; parse its telemetry line."""
    if not ensure_built():
        raise RuntimeError("verilator not available / build failed")
    args = [BIN, "+stream", f"+veto={veto}", f"+pclick={pclick}",
            f"+gates={gates}", f"+seed={seed}"]
    out = subprocess.run(args, cwd=HERE, capture_output=True, text=True).stdout
    line = next(l for l in out.splitlines() if l.startswith("STREAM"))
    d = {}
    for tok in line.split()[1:]:
        k, v = tok.split("=")
        d[k] = float(v) if ("." in v or "e" in v) else int(v)
    return d


if __name__ == "__main__":
    code, out = build_and_run()
    print(out)
    sys.exit(code)
