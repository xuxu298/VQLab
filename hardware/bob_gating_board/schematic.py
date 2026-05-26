"""Schematic drawing of one Bob detector channel (self-differencing front-end).

A programmatic, version-controlled schematic (schemdraw) of the H1 board: the discrete SPAD
bias-tee front-end with real component symbols, then the RF self-differencing chain. Designators
match the netlist (netlist.txt) and the BOM in docs/03 §5. Two identical channels; one is drawn.

Run:  python -m hardware.bob_gating_board.schematic   (from the repo root)
Output: demos/figures/h1_schematic.png
"""
from __future__ import annotations

import os

import schemdraw
import schemdraw.elements as elm

FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                   "demos", "figures", "h1_schematic.png")


def main() -> None:
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=11, unit=2.0)

        # === SPAD bias-tee front-end (discrete) =============================
        d += elm.SourceSin().right().label("GATE\n1.25 GHz", loc="left")
        d += elm.Capacitor().right().label("C1\n100pF", loc="bottom")
        d += (n1 := elm.Dot())                                    # SPAD cathode / bias node

        # bias-tee DC arm: RF choke up to the −V_DC bias source
        d.push()
        d += elm.Inductor2().up().length(2.6).label("L1 470nH\n(RF choke)", loc="right")
        d += elm.SourceV().up().length(2.4).label("−V_DC\n(AD5535B)", loc="right")
        d += elm.Ground()
        d.pop()

        # SPAD reverse-biased, cathode(top) -> anode(bottom) = readout node
        d += elm.Diode().down().length(2.6).reverse().label("D1 SPAD\n(IAG)", loc="left")
        d += (n2 := elm.Dot())
        d.push()
        d += elm.Resistor().down().length(1.8).label("R1\n50Ω", loc="right")
        d += elm.Ground()
        d.pop()

        # readout -> DC block -> splitter
        d += elm.Line().right().at(n2.center).length(1.2)
        d += elm.Capacitor().right().label("C2 100pF")
        d += (split := elm.RBox(w=2.4, h=1.1).right()
              .label("WILKINSON\nSPLITTER").fill("#eaf2f8"))

        # === self-differencing: subtract a 1-gate-period-delayed copy ========
        # subtractor as an op-amp-style difference block (clean 2-in/1-out anchors)
        sx, sy = split.end
        d += (sub := elm.Opamp(leads=True).anchor("in2").at((sx + 4.0, sy))
              .label("180° HYBRID\nΔ = A − B", loc="center", ofst=(0, 0), fontsize=9))

        # direct arm A -> inverting-style lower input (in2)
        d += elm.Line().at(split.end).to(sub.in2).color("#1a5276")
        d += elm.CurrentLabel(ofst=0.2).at(split.end).label("A (direct)", loc="bottom", fontsize=9)

        # delayed arm B: up, through the coax delay box, down into the upper input (in1)
        d += elm.Line().at(split.end).up(1.8).color("#922b21")
        d += (dl := elm.RBox(w=2.6, h=1.0).right()
              .label("COAX DELAY\nτ=0.80ns\n(1 gate period)", fontsize=8).fill("#fdebd0"))
        d += elm.Line().at(dl.end).tox(sub.in1[0] - 0.4).color("#922b21")
        d += elm.Line().toy(sub.in1).color("#922b21")
        d += elm.Line().to(sub.in1).color("#922b21").label("B (delayed)", loc="top", fontsize=9)

        # === LNA -> comparator -> LVDS event ================================
        d += elm.Line().right().at(sub.out).length(0.8)
        d += (lna := elm.Opamp(leads=True).anchor("in2").label("LNA\nPGA-103+", loc="center",
                                                              fontsize=9))
        d += elm.Ground().at(lna.in1)
        d += elm.Line().right().at(lna.out).length(0.8)
        d += (cmp := elm.Opamp(leads=True).anchor("in2").label("CMP\nADCMP572", loc="center",
                                                              fontsize=9))
        d += elm.Line().right().at(cmp.out).length(0.6)
        d += elm.Tag().right().label("LVDS\n→ TDC/FPGA", fontsize=9)
        # comparator threshold input
        d += elm.Line().left(1.2).at(cmp.in1)
        d += elm.Tag().left().label("V_th (DAC)", fontsize=9)

        d += elm.Tag().at((sx + 4.0, sy - 3.2)).label(
            "one of 2 identical channels · quench = gating-intrinsic · "
            "afterpulse veto in FPGA", fontsize=8)

    os.makedirs(os.path.dirname(FIG), exist_ok=True)
    d.save(os.path.abspath(FIG), dpi=130)
    print(f"[H1] wrote {os.path.abspath(FIG)}")


if __name__ == "__main__":
    main()
