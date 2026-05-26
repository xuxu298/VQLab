# Bob gating/quenching board — BOM & netlist (H1)

Per **channel**; the board carries **2 identical channels** (one Bob AMZI → 2 output-port
detectors, see `docs/03` §1). Quantities below are per-channel / per-board(×2).

Machine-readable netlist: [`bob_channel.net`](bob_channel.net) (KiCad-importable into Pcbnew:
*File → Import → Netlist*). RF blocks (U1 Wilkinson, U2 hybrid, DL1 delay) carry placeholder
`QResearch:` footprints — in layout they become either connectorised modules or microstrip
structures (controlled 50 Ω impedance); flagged for the layout pass.

| Ref | Value / Part | Function | Qty/ch | Qty/board | Notes |
|---|---|---|---|---|---|
| D1 | InGaAs/InP SPAD — **Laser Components IAG-series** / Wooriro (AMS) | single-photon avalanche diode | 1 | 2 | V_BR ~50–70 V, C_j ~0.3–1 pF; on TEC |
| L1 | 470 nH RF choke (0603, SRF > 2 GHz) | bias-tee DC arm | 1 | 2 | passes −V_DC, blocks RF |
| C1, C2 | 100 pF NP0 (0402) | DC blocks (gate / readout) | 2 | 4 | bias-tee RF arm + readout |
| R1 | 50 Ω (0402) | readout termination | 1 | 2 | matches readout to 50 Ω |
| U1 | Wilkinson splitter (DC–3 GHz) | split readout → A, B arms | 1 | 2 | module or microstrip |
| DL1 | semi-rigid coax, length-tuned **τ = 0.80 ns** | 1-gate-period delay | 1 | 2 | the SD core; phase-trim in test |
| U2 | 180° hybrid (DC–3 GHz) | analog subtract Δ = A − B | 1 | 2 | sets suppression ratio |
| U3 | **Mini-Circuits PGA-103+** | LNA (NF < 1 dB) | 1 | 2 | lifts the avalanche |
| U4 | **Analog Devices ADCMP572** | fast comparator → LVDS event | 1 | 2 | V_th from DAC |
| J1 | SMA | 1.25 GHz gate input | 1 | 2 | from gate-gen board |
| J2/J3/J4 | headers | −V_DC / V_th / LVDS out | 3 | 6 | board interfaces |

Shared (per board, not per channel):

| Ref | Part | Function |
|---|---|---|
| U5 | **Analog Devices ADN8834** + Peltier | SPAD TEC controller (−30…−40 °C, ±0.01 °C) |
| U6 | **Analog Devices AD5535B** (32-ch, 200 V HV DAC) | per-channel −V_DC bias (V_BR − V_ex) |

**Quench strategy:** gating-intrinsic (gate window ends → bias < breakdown → avalanche
self-quenches); afterpulse hold-off = FPGA gate-veto after each click + the 1-cycle SD dead
time. No active-quench ASIC needed at GHz gating.

**Next (layout pass):** assign real RF footprints / define the microstrip structures, set the
controlled-impedance stackup (50 Ω), and length-match the DL1 coax to 0.80 ns in fab + test.
