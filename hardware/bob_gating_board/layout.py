"""Programmatic KiCad PCB layout for the Bob self-differencing detector channel (H1, docs/03 §7).

This is the layout step done HEADLESS via the KiCad `pcbnew` Python API (no GUI): it turns the
captured netlist (`bob_channel.net`, 15 components / 13 nets) into a physical board and encodes the
parts of the layout that actually set this board's performance — the moat ([[qkd_moat_is_execution]]):

  * a 50 Ohm controlled-impedance microstrip stackup (trace width solved for the FR4 stackup),
  * the self-differencing DELAY LINE as a length-tuned meander = exactly one 1.25 GHz gate period
    (0.80 ns) of electrical delay (the SD core, docs/03 §3) — its physical length is computed from
    the substrate, then laid as a serpentine on the delay arm,
  * length-matched direct/delay arms into the 180 deg hybrid,
  * a ground reference pour (the microstrip return), board outline, and gerber + image export.

It is a first programmatic pass: footprints are simple in-code pads with the exact net pin names
(the netlist already carries the real vendor footprints for the fab-house pass); final RF tuning
(per-harmonic SD trim, exact phase match, impedance verification on the real stackup) is bench work.

Run:  python -m hardware.bob_gating_board.layout    (needs KiCad 6+; writes layout/ + a PNG render)
"""
from __future__ import annotations

import math
import os
import subprocess

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "layout")
FIGDIR = os.path.join(HERE, "..", "..", "demos", "figures")

# ---- electrical targets ---------------------------------------------------------------------
GATE_HZ = 1.25e9                 # Phase-1 gate rate (docs/03 §1)
GATE_PERIOD_S = 1.0 / GATE_HZ    # 0.80 ns — the SD delay target
Z0 = 50.0                        # ohm, RF system impedance
ER = 4.3                         # FR4 relative permittivity
H_MM = 0.20                      # top dielectric height to the inner ground plane (microstrip)
C0 = 299_792_458.0               # m/s


# ---- microstrip 50 ohm synthesis + delay-line length ----------------------------------------
def er_eff(w_mm: float) -> float:
    u = w_mm / H_MM
    return (ER + 1) / 2 + (ER - 1) / 2 * (1 + 12 / u) ** -0.5


def z0_microstrip(w_mm: float) -> float:
    u = w_mm / H_MM
    ee = er_eff(w_mm)
    if u <= 1:
        return 60 / math.sqrt(ee) * math.log(8 / u + u / 4)
    return 120 * math.pi / (math.sqrt(ee) * (u + 1.393 + 0.667 * math.log(u + 1.444)))


def solve_width_for_z0(target: float = Z0) -> float:
    lo, hi = 0.05, 5.0                       # bisect on width (Z0 decreases as w grows)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if z0_microstrip(mid) > target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


RF_W_MM = solve_width_for_z0()
EE = er_eff(RF_W_MM)
V_EFF = C0 / math.sqrt(EE)                    # propagation velocity on the microstrip
DELAY_LEN_MM = V_EFF * GATE_PERIOD_S * 1e3    # physical length for one gate period of delay


# ---- pcbnew helpers -------------------------------------------------------------------------
def mm(x: float, y: float):
    return pcbnew.wxPointMM(float(x), float(y))


def make_footprint(board, ref, value, pads, body=(2.0, 2.0)):
    """Build a simple in-code footprint: pads = [(name, dx_mm, dy_mm)] relative to the centre."""
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(ref)
    fp.SetValue(value)
    for name, dx, dy in pads:
        pad = pcbnew.PAD(fp)
        pad.SetSize(pcbnew.wxSizeMM(0.8, 0.8))
        pad.SetShape(pcbnew.PAD_SHAPE_RECT)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetLayerSet(pad.SMDMask())
        pad.SetName(name)
        pad.SetPos0(mm(dx, dy))
        pad.SetPosition(mm(dx, dy))      # absolute set again after we move the footprint
        fp.Add(pad)
    fp.Value().SetVisible(False)         # keep the silk readable — show reference only, small
    fp.Reference().SetTextSize(pcbnew.wxSizeMM(0.9, 0.9))
    board.Add(fp)
    return fp


def place(fp, x, y):
    fp.SetPosition(mm(x, y))
    for pad in fp.Pads():
        off = pad.GetPos0()
        pad.SetPosition(pcbnew.wxPoint(fp.GetPosition().x + off.x, fp.GetPosition().y + off.y))


def pad_xy(fp, name):
    for pad in fp.Pads():
        if pad.GetName() == name:
            p = pad.GetPosition()
            return p.x, p.y
    raise KeyError(f"{fp.GetReference()} has no pad {name}")


def build():
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)             # F.Cu (RF) / In1 GND / In2 power / B.Cu (LF)

    # nets ------------------------------------------------------------------------------------
    # NOTE: the netlist models the delay (DL1) as a discrete element; in this layout we realize it
    # as a length-tuned on-board MEANDER (docs/03 §7: "trace/coax"), so the delay arm is one net
    # (U1.OUT2 -> meander -> U2.B) rather than two stubs around a connectorized coax.
    netnames = ["GATE_IN", "N_CATHODE", "BIAS_HV", "N_READOUT", "N_RF", "ARM_A_DIRECT",
                "ARM_B", "SD_OUT", "LNA_OUT", "VTH", "LVDS_OUT", "GND"]
    nets = {}
    for n in netnames:
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni

    # footprints (pad names match bob_channel.net) -------------------------------------------
    fps = {}
    fps["J1"] = make_footprint(board, "J1", "SMA gate in", [("1", 0, 0), ("2", 0, 2.5)])
    fps["C1"] = make_footprint(board, "C1", "100pF", [("1", -0.5, 0), ("2", 0.5, 0)])
    fps["L1"] = make_footprint(board, "L1", "470nH", [("1", 0, -0.6), ("2", 0, 0.6)])
    fps["D1"] = make_footprint(board, "D1", "InGaAs SPAD", [("A", 0, 0.8), ("K", 0, -0.8)])
    fps["J2"] = make_footprint(board, "J2", "-V_DC", [("1", 0, -1.0), ("2", 0, 1.0)])
    fps["U6"] = make_footprint(board, "U6", "AD5535B", [("VOUT", 1.5, 0), ("2", -1.5, 0)], body=(4, 4))
    fps["R1"] = make_footprint(board, "R1", "50R", [("1", 0, -0.5), ("2", 0, 0.5)])
    fps["C2"] = make_footprint(board, "C2", "100pF", [("1", -0.5, 0), ("2", 0.5, 0)])
    fps["U1"] = make_footprint(board, "U1", "Wilkinson", [("IN", -1.5, 0), ("OUT1", 1.5, -1.0),
                                                          ("OUT2", 1.5, 1.0)], body=(3, 3))
    fps["U2"] = make_footprint(board, "U2", "180deg hybrid", [("A", -1.5, -1.0), ("B", -1.5, 1.0),
                                                              ("DELTA", 1.5, 0)], body=(3, 3))
    fps["U3"] = make_footprint(board, "U3", "PGA-103+", [("IN", -1.2, 0), ("OUT", 1.2, 0),
                                                         ("GND", 0, 1.2)], body=(2.5, 2.5))
    fps["U4"] = make_footprint(board, "U4", "ADCMP572", [("INP", -1.5, -0.6), ("INN", -1.5, 0.6),
                                                         ("OUT", 1.5, 0), ("GND", 0, 1.5)], body=(3, 3))
    fps["J3"] = make_footprint(board, "J3", "V_th", [("1", 0, -1.0), ("2", 0, 1.0)])
    fps["J4"] = make_footprint(board, "J4", "LVDS out", [("1", 0, -1.0), ("2", 0, 1.0)])

    # placement (signal flow left -> right), mm --------------------------------------------------
    pos = {"J1": (8, 22), "C1": (15, 22), "D1": (22, 22), "L1": (22, 14), "J2": (9, 11),
           "U6": (15, 11), "C2": (28, 22), "R1": (28, 29), "U1": (35, 22),
           "U2": (67, 22), "U3": (75, 22), "U4": (83, 22), "J3": (72, 31), "J4": (91, 22)}
    for ref, (x, y) in pos.items():
        place(fps[ref], x, y)

    # assign pads to nets (mirrors bob_channel.net) ------------------------------------------
    wiring = {
        "GATE_IN": [("J1", "1"), ("C1", "1")],
        "N_CATHODE": [("C1", "2"), ("L1", "2"), ("D1", "K")],
        "BIAS_HV": [("L1", "1"), ("J2", "1"), ("U6", "VOUT")],
        "N_READOUT": [("D1", "A"), ("R1", "1"), ("C2", "1")],
        "N_RF": [("C2", "2"), ("U1", "IN")],
        "ARM_A_DIRECT": [("U1", "OUT1"), ("U2", "A")],
        "ARM_B": [("U1", "OUT2"), ("U2", "B")],          # the delay arm = the meander (below)
        "SD_OUT": [("U2", "DELTA"), ("U3", "IN")],
        "LNA_OUT": [("U3", "OUT"), ("U4", "INP")],
        "VTH": [("J3", "1"), ("U4", "INN")],
        "LVDS_OUT": [("U4", "OUT"), ("J4", "1")],
        "GND": [("J1", "2"), ("J2", "2"), ("J3", "2"), ("J4", "2"), ("R1", "2"),
                ("U3", "GND"), ("U4", "GND")],
    }
    for net, pins in wiring.items():
        for ref, pad in pins:
            for p in fps[ref].Pads():
                if p.GetName() == pad:
                    p.SetNet(nets[net])

    # routing ---------------------------------------------------------------------------------
    rf_w = pcbnew.FromMM(RF_W_MM)
    sig_w = pcbnew.FromMM(0.25)

    def track(x1, y1, x2, y2, net, width, layer=pcbnew.F_Cu):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.wxPoint(int(x1), int(y1)))
        t.SetEnd(pcbnew.wxPoint(int(x2), int(y2)))
        t.SetWidth(width)
        t.SetLayer(layer)
        t.SetNet(net)
        board.Add(t)

    def route(refpads, net, width):
        pts = [pad_xy(fps[r], p) for r, p in refpads]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            track(x1, y1, x2, y2, net, width)

    # straight RF nets (50 ohm width)
    route([("C2", "2"), ("U1", "IN")], nets["N_RF"], rf_w)
    route([("U1", "OUT1"), ("U2", "A")], nets["ARM_A_DIRECT"], rf_w)   # the direct arm
    route([("U2", "DELTA"), ("U3", "IN")], nets["SD_OUT"], rf_w)
    route([("U3", "OUT"), ("U4", "INP")], nets["LNA_OUT"], rf_w)
    # low-frequency / DC nets (thin)
    route([("J1", "1"), ("C1", "1")], nets["GATE_IN"], rf_w)
    route([("C1", "2"), ("D1", "K")], nets["N_CATHODE"], sig_w)
    route([("L1", "2"), ("D1", "K")], nets["N_CATHODE"], sig_w)
    route([("U6", "VOUT"), ("J2", "1")], nets["BIAS_HV"], sig_w)
    route([("J2", "1"), ("L1", "1")], nets["BIAS_HV"], sig_w)
    route([("D1", "A"), ("C2", "1")], nets["N_READOUT"], sig_w)
    route([("D1", "A"), ("R1", "1")], nets["N_READOUT"], sig_w)
    route([("J3", "1"), ("U4", "INN")], nets["VTH"], sig_w)
    route([("U4", "OUT"), ("J4", "1")], nets["LVDS_OUT"], sig_w)

    # the SELF-DIFFERENCING delay line: the delay arm must be LONGER than the direct arm by exactly
    # one gate period (the periodic gate transient then cancels; the aperiodic avalanche survives).
    dax, day = pad_xy(fps["U1"], "OUT1")
    dbx, dby = pad_xy(fps["U2"], "A")
    direct_len_mm = pcbnew.ToMM(int(math.hypot(dax - dbx, day - dby)))
    meander_len_mm = route_meander(board, track, fps, nets["ARM_B"], rf_w,
                                   target_mm=DELAY_LEN_MM + direct_len_mm)
    silk_text(board, "DL1 delay meander: arm_B - arm_A = 0.80 ns = 132.7 mm", 30, 39, 1.0)
    silk_text(board, "Bob SD detector channel - 50 ohm microstrip - H1/H2", 6, 8, 1.2)

    # ground pour on the inner plane (microstrip reference) -----------------------------------
    pour_ok = ground_pour(board, nets["GND"], 4, 4, 94, 38)

    # board outline ---------------------------------------------------------------------------
    for x1, y1, x2, y2 in [(3, 5, 99, 5), (99, 5, 99, 43), (99, 43, 3, 43), (3, 43, 3, 5)]:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(x1, y1)); s.SetEnd(mm(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.15))
        board.Add(s)

    return board, meander_len_mm, direct_len_mm, pour_ok


def route_meander(board, track, fps, net, width, target_mm):
    """Lay the delay arm as a serpentine on F.Cu whose TOTAL copper length (U1.OUT2 -> ... -> U2.B)
    equals target_mm = one 1.25 GHz gate period of electrical delay (the SD core, docs/03 §3).

    Greedily lays serpentine passes; before each pass it reserves the straight-line run to U2.B,
    and trims the final pass so the total lands exactly on target. Returns the achieved length (mm).
    """
    import math as _m

    def dist(ax, ay, bx, by):
        return _m.hypot(ax - bx, ay - by)

    sx, sy = pad_xy(fps["U1"], "OUT2")
    bx, by = pad_xy(fps["U2"], "B")
    x_lo, x_hi = pcbnew.FromMM(43), pcbnew.FromMM(61)
    pitch = pcbnew.FromMM(1.1)
    target = pcbnew.FromMM(target_mm)

    seg_len = 0.0
    prev = (sx, sy)
    track(sx, sy, x_lo, pcbnew.FromMM(26), net, width)            # drop from U1.OUT2 into the field
    seg_len += dist(sx, sy, x_lo, pcbnew.FromMM(26))
    prev = (x_lo, pcbnew.FromMM(26))
    y = pcbnew.FromMM(26)
    going_right = True
    while True:
        nx = x_hi if going_right else x_lo
        # would a full horizontal pass (+ the eventual exit to U2.B) overshoot the target?
        if seg_len + abs(nx - prev[0]) + dist(nx, y, bx, by) >= target:
            lo, hi = 0.0, abs(nx - prev[0])          # trim this pass so total == target
            for _ in range(60):
                L = 0.5 * (lo + hi)
                ex = prev[0] + (L if going_right else -L)
                if seg_len + L + dist(ex, y, bx, by) > target:
                    hi = L
                else:
                    lo = L
            L = 0.5 * (lo + hi)
            ex = prev[0] + (L if going_right else -L)
            track(prev[0], prev[1], ex, y, net, width)
            seg_len += L
            prev = (ex, y)
            break
        track(prev[0], prev[1], nx, y, net, width)
        seg_len += abs(nx - prev[0])
        prev = (nx, y)
        ny = y + pitch
        track(prev[0], prev[1], prev[0], ny, net, width)          # the turn
        seg_len += pitch
        prev = (prev[0], ny)
        y = ny
        going_right = not going_right
        if y > pcbnew.FromMM(37):                                  # safety: out of the field
            break
    track(prev[0], prev[1], bx, by, net, width)                   # exit to the hybrid
    seg_len += dist(prev[0], prev[1], bx, by)
    return pcbnew.ToMM(seg_len)


def silk_text(board, text, x, y, size_mm):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetPosition(mm(x, y))
    t.SetTextSize(pcbnew.wxSizeMM(size_mm, size_mm))
    t.SetHorizJustify(pcbnew.GR_TEXT_HJUSTIFY_LEFT)
    board.Add(t)


def ground_pour(board, gnd_net, x, y, w, h):
    try:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(pcbnew.In1_Cu)
        zone.SetNetCode(gnd_net.GetNetCode())
        v = pcbnew.wxPoint_Vector()
        for px, py in [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]:
            v.append(mm(px, py))
        zone.AddPolygon(v)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        return True
    except Exception as e:        # zone API varies across KiCad versions — non-fatal
        print(f"  (ground pour skipped: {e})")
        return False


def export(board):
    os.makedirs(OUTDIR, exist_ok=True)
    os.makedirs(FIGDIR, exist_ok=True)
    pcb_path = os.path.join(OUTDIR, "bob_channel.kicad_pcb")
    pcbnew.SaveBoard(pcb_path, board)

    # gerbers (what the fab needs)
    pctl = pcbnew.PLOT_CONTROLLER(board)
    po = pctl.GetPlotOptions()
    po.SetOutputDirectory(OUTDIR)
    po.SetPlotFrameRef(False)
    for layer, tag in [(pcbnew.F_Cu, "F_Cu"), (pcbnew.In1_Cu, "In1_Cu"),
                       (pcbnew.B_Cu, "B_Cu"), (pcbnew.Edge_Cuts, "Edge_Cuts")]:
        pctl.SetLayer(layer)
        pctl.OpenPlotfile(tag, pcbnew.PLOT_FORMAT_GERBER, tag)
        pctl.PlotLayer()
    pctl.ClosePlot()
    for tag in ("F_Cu", "In1_Cu", "B_Cu", "Edge_Cuts"):       # tidy the leading-dash names
        src = os.path.join(OUTDIR, f"-{tag}.gbr")
        if os.path.exists(src):
            os.replace(src, os.path.join(OUTDIR, f"bob_channel-{tag}.gbr"))

    # one combined SVG (Edge + copper + silk) for a human render
    before = set(f for f in os.listdir(OUTDIR) if f.endswith(".svg"))
    pctl2 = pcbnew.PLOT_CONTROLLER(board)
    po2 = pctl2.GetPlotOptions()
    po2.SetOutputDirectory(OUTDIR)
    po2.SetPlotFrameRef(False)
    pctl2.SetColorMode(True)
    pctl2.OpenPlotfile("render", pcbnew.PLOT_FORMAT_SVG, "render")
    for layer in (pcbnew.Edge_Cuts, pcbnew.In1_Cu, pcbnew.F_Cu, pcbnew.F_SilkS, pcbnew.F_Fab):
        pctl2.SetLayer(layer)
        pctl2.PlotLayer()
    pctl2.ClosePlot()
    new_svgs = [f for f in os.listdir(OUTDIR) if f.endswith(".svg")]
    produced = next((os.path.join(OUTDIR, f) for f in new_svgs if f not in before), None)
    png = os.path.join(FIGDIR, "h1_pcb_layout.png")
    if produced:
        subprocess.run(["rsvg-convert", "-b", "white", "-z", "4", "-o", png, produced], check=False)
    return pcb_path, png


def main():
    print("Bob detector channel — programmatic KiCad layout (H1)")
    print(f"  stackup            : 4-layer FR4, Er={ER}, microstrip h={H_MM} mm to inner GND")
    print(f"  50 ohm trace width : {RF_W_MM:.3f} mm   (microstrip, Er_eff={EE:.2f})")
    print(f"  gate period        : {GATE_PERIOD_S*1e9:.2f} ns @ {GATE_HZ/1e9:.2f} GHz")
    print(f"  delay-line length  : {DELAY_LEN_MM:.1f} mm  (v_eff={V_EFF/1e8:.2f}e8 m/s)")
    board, meander_mm, direct_mm, pour_ok = build()
    delta_mm = meander_mm - direct_mm
    print(f"  direct arm (arm_A) : {direct_mm:.1f} mm")
    print(f"  delay arm  (arm_B) : {meander_mm:.1f} mm (meander)")
    print(f"  arm_B - arm_A      : {delta_mm:.1f} mm  => {delta_mm/V_EFF/1e3*1e9:.3f} ns "
          f"(target {GATE_PERIOD_S*1e9:.2f} ns)")
    print(f"  ground pour        : {'filled (In1.Cu)' if pour_ok else 'skipped'}")
    pcb, png = export(board)
    print(f"  wrote board        : {pcb}")
    print(f"  wrote render       : {png}")


if __name__ == "__main__":
    main()
