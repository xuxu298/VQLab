# Bob Detector — Gating / Quenching Board (subsystem H1)

**Version:** v0.1 · **Date:** 2026-05-26
**Scope:** the hardest, most-differentiating subsystem of the QKD device — the GHz-gated
InGaAs/InP SPAD front-end with **self-differencing** gate-transient cancellation.
**Parent:** [`01_architecture_and_bom.md`](01_architecture_and_bom.md) §4.2 (BD2).
**Validation toolchain:** ngspice (analog sim) + the validated `qsim` finite-key model.

> ⚠️ Device-level electrical values (SPAD capacitance, breakdown, avalanche charge) are
> **representative/literature-class** and MUST be tightened against the chosen SPAD's
> datasheet + measurements before layout. Provenance is cited inline.

> 📖 **Cách đọc:** mỗi phần có bảng/spec tiếng Anh + khối **"Giải thích"** tiếng Việt ngay sau.
> Đây là board **khó nhất và là lõi moat** của cả dự án — chỗ "tự làm được hay không" quyết định
> mình có sản phẩm thật hay chỉ đi mua đồ về lắp.

---

## 0. Why this board is the moat

The architecture (decoy-BB84, AMZI, fiber) is public knowledge; anyone can buy the optics.
The defensible engineering is in **making a single-photon detector actually work at GHz rates** —
and the central obstacle is a purely electrical one that this board solves.

> **Giải thích — tại sao board này là "hào" (moat):** kiến trúc QKD ai cũng biết, linh kiện quang
> ai cũng mua được. Cái **khó và khác biệt** là làm cho đầu dò đơn-photon chạy được ở tốc độ GHz.
> Rào cản chính là một vấn đề **thuần điện tử** (xung dội của cổng) mà board này xử lý — làm chủ
> được nó = làm chủ thứ đối thủ không mua sẵn được. Xem [[qkd_moat_is_execution]].

---

## 1. Resolved architecture decisions (closes `01` §9 open questions)

| # | Question | Decision (Phase 1) | Reasoning |
|---|---|---|---|
| 1 | Detector channels — 2 vs 4 | **2 channels** | One-way phase/time-bin BB84 (Toshiba/Cambridge style): a single Bob AMZI with 2 output-port detectors. The Z (key) bit comes from the **arrival time-slot** (one detector + time-tagging distinguishes early/late), the X (check) bit from **which port** clicked. 4 detectors (full active basis) doubles SPAD + TDC cost for marginal Phase-1 benefit. Keeps this board to 2 identical channels. |
| 2 | Sync strategy | **Dedicated 1310 nm optical sync, WDM-combined onto the same dark fiber** | A bright 1310 nm pulse + fast PIN + PLL clock recovery is the proven, deterministic metro approach; CWDM-coupling it with the 1550 nm quantum channel avoids leasing a second fiber. Clock-recovery off the quantum channel is too photon-starved; White Rabbit adds Ethernet-timing complexity not needed at metro range. |
| 3 | Phase-1 demo span | **25 km assumed** (10–50 km envelope) | Drives µ≈0.5 and the detector tuning. **Flag:** the telco confirms the exact dark-fiber span; the qsim sweep (§6) already spans 1–120 km so re-pointing is a one-line change. |

> **Giải thích — 3 quyết định kiến trúc:** (1) **2 kênh đầu dò** — dùng sơ đồ BB84 pha/time-bin một
> chiều: 1 giao thoa kế ở Bob + 2 đầu dò ở 2 cổng ra; bit khóa (Z) đọc từ **khe thời gian** photon
> tới, bit kiểm (X) đọc từ **cổng nào** kêu. 4 đầu dò tốn gấp đôi mà Phase-1 lợi không đáng. (2)
> **Sync 1310 nm ghép chung sợi** — xung sáng 1310 nm + PIN nhanh + khóa pha, ghép CWDM chung sợi tối
> với kênh lượng tử 1550 nm để khỏi thuê 2 sợi. (3) **25 km** giả định (telco chốt sau); sim đã quét
> 1–120 km nên đổi rất dễ.

---

## 2. The problem: the gate transient buries the avalanche

To suppress dark counts and afterpulsing, the SPAD is biased above breakdown only during a
short **gate** synchronised to the expected photon arrival. At 1.25 GHz the gate is effectively
a fast sinusoid of amplitude V_g across the diode. The SPAD junction capacitance C_j responds
with a **displacement current** i = C_j · dV/dt that, into a 50 Ω readout, produces a transient
of order

    v_transient ≈ 50 · C_j · V_g · 2πf  ≈  50 · 0.5 pF · 3 V · 2π·1.25 GHz ≈ **0.58 V**,

whereas a single-photon avalanche of ~50 fC over ~80 ps is only ~**30 mV**. The signal is buried
~26 dB *below* the gate feedthrough — undetectable by a simple discriminator.

> **Giải thích — vấn đề cốt lõi:** để giảm nhiễu, ta chỉ "mở cổng" SPAD trong khoảnh khắc ngắn,
> đúng lúc photon dự kiến tới. Nhưng mở/đóng cổng cực nhanh (1.25 GHz) làm **điện dung của diode**
> phun ra một **dòng xung lớn** (~0.58 V), trong khi tín hiệu photon thật chỉ ~30 mV. Tức tín hiệu
> bị **chôn vùi** dưới xung cổng ~26 dB → đầu dò thường không thấy gì. Phải khử xung cổng đi.

---

## 3. The solution: self-differencing (SD)

The gate transient is **periodic** (identical every gate); the avalanche is **aperiodic** (in
one gate only). Self-differencing [Yuan et al., APL 91, 041114 (2007); Comandar et al.,
arXiv:1412.1586] splits the detector output and subtracts a copy delayed by **exactly one gate
period** (0.8 ns @ 1.25 GHz, a length-tuned matched coax). The periodic transient cancels; the
avalanche survives (plus an inverted "ghost" one period later, vetoed in the FPGA).

```
                        ┌──────────────── direct ──────────────┐
 SPAD ──HV bias-tee──► readout ──50Ω splitter                   ├─►(−)
   ▲ 1.25GHz gate                  └── coax delay = 1 gate T ──►(+)┘ 180° hybrid / diff
   │ (sine, via bias-tee)                                          │  = self-differenced out
   │                                                               ▼
 −V_DC (≈ V_BR − V_ex)                                   LNA ─► fast comparator ─► LVDS event ─► TDC/FPGA
```

> **Giải thích — cách khử (self-differencing):** xung cổng **lặp lại y hệt mỗi chu kỳ**, còn xung
> photon **chỉ xuất hiện một lần**. SD tách tín hiệu làm 2 đường, **trễ một đường đúng 1 chu kỳ cổng**
> (0.8 ns) rồi **trừ đi nhau**: phần lặp (xung cổng) triệt tiêu, phần một-lần (photon) còn lại. Có một
> "bóng ma" đảo dấu 1 chu kỳ sau — FPGA bỏ qua. Đây chính là kỹ thuật Toshiba/Cambridge dùng để chạy
> SPAD ở GHz.

---

## 4. ngspice simulation — the cancellation works

`hardware/bob_gating_board/sd_frontend.cir` models the gate-coupled junction capacitance, an
aperiodic avalanche current, and the SD split/delay/subtract network (with a realistic 2 %
delay-line amplitude imbalance). `simulate.py` runs it and quantifies the result:

| Quantity | Value |
|---|---|
| Raw gate transient (buries avalanche) | **578 mV** |
| SD residual transient | **11.6 mV** |
| Gate-transient suppression | **34 dB** |
| Avalanche peak after SD | **40 mV** |
| Avalanche / transient **before** SD | 0.069 (buried) |
| Avalanche / residual **after** SD | **3.5** (discriminable) |

Self-differencing flips the avalanche from 7 % of the transient (undetectable) to 3.5× the
residual (cleanly discriminable). 34 dB matches the basic-SD literature range (20–40 dB; >65 dB
with per-harmonic amplitude/phase tuning). Figure: `demos/figures/h1_sd_cancellation.png`.

> **Giải thích — mô phỏng ngspice chứng minh nó chạy:** tao dựng mạch trong ngspice (file `.cir`),
> mô phỏng đúng hiện tượng: trước SD xung cổng 578 mV nuốt chửng photon 40 mV; sau SD xung cổng chỉ
> còn 11.6 mV (**giảm 34 dB**) nên photon **nhô lên gấp 3.5 lần** nền → đầu dò phân biệt được. Đây là
> đúng tinh thần dự án: **mô phỏng vật lý thật trước khi hàn mạch**.

---

## 4a. Schematic & netlist (capture)

The circuit is captured as a version-controlled schematic and a machine-readable netlist:

- **Schematic** (one of 2 identical channels): `demos/figures/h1_schematic.png`, generated by
  `hardware/bob_gating_board/schematic.py` (schemdraw). Shows the discrete SPAD bias-tee
  (C1/L1/D1/R1), the Wilkinson split, the τ=0.80 ns coax delay arm, the 180° hybrid
  (Δ = A − B), and the LNA → comparator → LVDS chain.
- **Netlist**: `hardware/bob_gating_board/bob_channel.net` — a KiCad-importable netlist
  (15 components, 13 nets) ready for *Pcbnew → Import Netlist* to start PCB layout.
- **BOM**: `hardware/bob_gating_board/BOM.md` — per-channel + per-board (×2) parts with real
  part numbers, plus the board-level TEC (ADN8834) and HV-DAC (AD5535B) support ICs.

The RF blocks (Wilkinson, hybrid, coax delay) carry placeholder `QResearch:` footprints; in
the layout pass they become connectorised modules or controlled-impedance microstrip
structures. The PCB layout is done **headless** (see §4b) via KiCad's `pcbnew` Python API — no
GUI needed — with the netlist as the hand-off.

> **Giải thích — bản vẽ & netlist:** mạch được "chụp" thành (1) **bản vẽ schematic** (file PNG sinh
> bằng `schematic.py`, xem được, có designator + giá trị), (2) **netlist** import thẳng vào KiCad
> Pcbnew để bắt đầu layout PCB, và (3) **BOM** part-number thật. Khối RF (splitter/hybrid/dây trễ)
> để footprint tạm; vào layout thành module hoặc đường microstrip 50 Ω. Bước layout PCB chạy
> **headless** (§4b) bằng API Python `pcbnew` của KiCad — không cần GUI.

## 4b. PCB layout (programmatic, headless)

`hardware/bob_gating_board/layout.py` turns the netlist into a physical board with the KiCad
`pcbnew` Python API — **no GUI** — encoding the layout choices that set this board's performance
(the moat, [[qkd_moat_is_execution]]):

- **50 Ω controlled-impedance microstrip.** A 4-layer FR4 stackup (signal / inner GND / power /
  signal); the RF trace width is *solved* for 50 Ω from the microstrip model — **0.392 mm** at
  Er=4.3, h=0.2 mm (Er_eff≈3.27).
- **The self-differencing delay line.** Realised as a **length-tuned meander** (the docs/03 §7
  "trace" option). Its physical length is computed from the substrate velocity
  (v_eff≈1.66×10⁸ m/s), and the delay arm is laid so that **arm_B − arm_A = 132.7 mm = exactly
  one 1.25 GHz gate period (0.80 ns)** — the condition that cancels the periodic gate transient
  while the aperiodic avalanche survives (§3). The discrete `DL1` coax is thus absorbed into the
  board as copper.
- Ground pour (the microstrip return), board outline, and **Gerber export** (`F_Cu`, `In1_Cu`,
  `B_Cu`, `Edge_Cuts`) + an SVG/PNG render: `demos/figures/h1_pcb_layout.png`.

`tests/test_layout.py` guards the 50 Ω width and the one-gate-period delay (auto-skipped without
KiCad). This is a first programmatic pass: the in-code footprints carry the exact net pin names
(the netlist already names the real vendor footprints for the fab-house revision), and final RF
tuning — per-harmonic SD trim, exact phase match, impedance verification on the real stackup — is
bench work. But placement, 50 Ω routing, the tuned delay, the pour, and manufacturable gerbers all
come straight out of the script.

> **Giải thích — layout PCB tự động, không cần GUI:** `layout.py` biến netlist thành board vật lý
> bằng API Python `pcbnew`. Nó **giải** bề rộng trace cho 50 Ω (0,392 mm trên FR4), và đặt **dây trễ
> self-differencing thành đường microstrip uốn khúc (meander) dài đúng 132,7 mm = 0,80 ns = 1 chu kỳ
> cổng** (điều kiện để khử xung cổng tuần hoàn mà giữ lại thác photon). Kèm đổ đồng ground, viền board,
> và xuất **Gerber** (file nhà máy cần) + ảnh render `h1_pcb_layout.png`. `tests/test_layout.py` canh
> hai con số sống còn (50 Ω + độ trễ 1 chu kỳ). Đây là bản layout đầu: tinh chỉnh RF cuối (trim từng
> hài, khớp pha, kiểm trở kháng trên stackup thật) là việc trên bàn đo — nhưng đặt linh kiện, đi dây
> 50 Ω, dây trễ tuned, đổ đồng và gerber chế tạo được đều ra thẳng từ script.

## 5. Component selection (per channel, ×2)

| Ref | Function | Representative part | Key spec | Notes |
|---|---|---|---|---|
| SPAD | InGaAs/InP single-photon APD | Laser Components IAG-series / Wooriro SPAD (via AMS) | V_BR ~50–70 V, C_j ~0.3–1 pF, η 25–60 % | bare APD; gated Geiger mode |
| HV bias | adjustable −V_DC source | HV DAC (AD5535B) + precision op-amp + RC filter | −60 V, <1 mV ripple, fine step | sets excess bias V_ex |
| Bias-tee | combine DC bias + RF gate, extract readout | wideband RF choke + DC-block (Coilcraft / Mini-Circuits) | DC–GHz | the gate enters and the signal exits here |
| Gate gen | 1.25 GHz sine gate | FPGA SERDES ÷ PLL → bandpass → RF driver (Qorvo/Mini-Circuits) | low phase noise | locked to system clock |
| Splitter | power split readout | Wilkinson / resistive | DC–3 GHz, 50 Ω | feeds direct + delay arms |
| Delay line | one-gate-period delay | semi-rigid coax, length-tuned | TD = 0.8 ns ±ps | the SD core; phase-matched |
| Subtractor | analog subtraction | 180° hybrid (Mini-Circuits) or balun + diff amp | wideband, amplitude/phase balance | sets the suppression ratio |
| LNA | low-noise amplification | Mini-Circuits PGA-103+ class | NF <1 dB, GHz BW | lifts the avalanche |
| Discriminator | avalanche → digital event | ADCMP572/580 fast comparator | ps timing, LVDS/LVPECL out | threshold = DAC-set |
| TEC | cool the SPAD | ADI ADN8834 + Peltier | −30…−40 °C, ±0.01 °C | dark-count control |

Quenching is **gating-intrinsic** (the gate window ends → bias drops below breakdown → the
avalanche self-quenches); afterpulse hold-off is handled by an **FPGA gate-veto** after each
click + the one-cycle SD dead time — no separate active-quench ASIC needed at GHz gating.

> **Giải thích — chọn linh kiện (mỗi kênh, ×2):** bảng liệt kê đúng từng khối + linh kiện đại diện
> (nhà cung cấp hiện hành). Điểm đáng chú ý: **không cần ASIC dập (quench) riêng** — vì gating GHz
> thì hết cửa sổ cổng là điện áp tụt dưới ngưỡng → thác **tự tắt**; afterpulse thì FPGA "khóa cổng"
> vài nhịp sau mỗi lần kêu. Dây trễ coax (delay line) là **trái tim** của SD — phải cắt đúng chiều
> dài để trễ chuẩn 0.8 ns, sai một chút là khử kém.

---

## 6. Design validation via qsim — is this detector good enough?

Feeding the verified detector parameters (PDE 30 %, p_dark 8×10⁻⁷/gate, e_d 1 %, 1.25 GHz)
into qsim's validated 1-decoy finite-key model (`validate_with_qsim.py`):

| Distance | Link loss | QBER | Finite-key SKR |
|---|---|---|---|
| 10 km | 5.5 dB | 1.00 % | ~15.2 Mbps |
| **25 km (Phase 1)** | **8.5 dB** | **1.00 %** | **~8.1 Mbps** |
| 50 km | 13.5 dB | 1.01 % | ~2.7 Mbps |
| 75 km | 18.5 dB | 1.03 % | ~0.85 Mbps |

QBER ~1 % is dominated by the AMZI misalignment (98 % visibility), not the detector — dark
counts are negligible at metro loss. The detector is **more than adequate**: the verified
30 %-PDE self-differencing module at 1.25 GHz yields **Mbps-class** key rate, well above the
conservative "tens–hundreds kbps" target in `01` §0 (which assumed an older 20 %/lower-rate
detector). Figure: `demos/figures/h1_designed_detector_skr.png`.

> **Giải thích — sim kiểm tra lại thiết kế:** đút thông số đầu dò vừa chốt vào mô hình khóa-hữu-hạn
> của qsim (chính code đã khớp Rusca 2018). Kết quả: **25 km → QBER 1.0 %, ~8 Mbps**. QBER chủ yếu do
> giao thoa kế (visibility 98 %), không phải đầu dò; nhiễu tối không đáng kể ở cự ly metro. Kết luận:
> đầu dò **dư sức** — còn vượt mục tiêu cũ. Đây là **vòng lặp thiết kε→sim→validate** mà nền tảng
> sim sinh ra để phục vụ.

---

## 6a. FPGA firmware — gate-veto + ghost-reject + timestamp (H2)

The analog front-end (§3) delivers at most one LVDS comparator event per gate period; the FPGA
turns that raw stream into clean, time-tagged single-photon detections. Synthesizable Verilog in
`hardware/bob_fpga/bob_gating.v`, validated in **Verilator**:

- **Ghost-reject.** Self-differencing leaves an inverted copy of each avalanche exactly one gate
  period later (§3). The firmware always vetoes the gate immediately after an accepted click —
  independent of the afterpulse setting (it is an SD artifact, not afterpulsing).
- **Gate-veto (afterpulse hold-off).** After each accepted click the firmware holds off
  `veto_cycles` gates. This length is **not free**: `veto_cycles = round(tau_dead · gate_rate)`,
  the *same* dead time qsim's finite-key model uses — for `ingaas_sd` (3 ns dead time, 1.25 GHz)
  that is **4 gates ≈ 3.2 ns**. Non-paralyzable: clicks inside the window do not extend it.
- **Timestamp.** Each accepted photon is tagged with the running gate index and strobed out
  (`event_valid` + `event_ts`) — the time-tag Bob sifts/aligns on; serialized back over LVDS.

Two-tier validated like the rest of the project: (1) a self-checking Verilator testbench
(`sim_main.cpp`, **26 checks / 0 fail**) pins the behaviour — single photon → one timestamp,
ghost rejected, afterpulse window + exact re-arm timing, disarm freezes the counter, saturated
throughput = 1/(veto+1), monotonic timestamps; (2) `validate_with_qsim.py` closes the
**hardware↔sim loop** — it derives `veto_cycles` from the qsim detector's `tau_dead` and confirms
the firmware-enforced dead time matches, and that the firmware's measured throttling follows the
non-paralyzable dead-time law `m = r/(1 + r·veto)` to <0.3%. Same discipline as the ngspice loop
in §4/§6. `tests/test_firmware.py` runs both (auto-skipped without Verilator).

> **Giải thích — firmware FPGA:** mạch analog mỗi chu kỳ cổng đưa ra tối đa một sự kiện; FPGA làm
> ba việc mạch không làm được: (1) **loại "bóng ma"** mà self-differencing sinh ra đúng 1 chu kỳ sau
> mỗi photon; (2) **khóa cổng** `veto_cycles` nhịp sau mỗi click để chặn afterpulse — độ dài này lấy
> đúng từ `tau_dead` của qsim (`= round(tau_dead·gate_rate)` = 4 nhịp ≈ 3,2 ns), không phải số tùy ý;
> (3) **đóng dấu thời gian** mỗi photon (chỉ số cổng) để Bob sàng/đồng bộ với Alice. Kiểm chứng 2 tầng
> như cả dự án: testbench Verilator (26 kiểm tra, 0 lỗi) + vòng lặp **phần cứng↔sim** khớp luật
> thời-gian-chết với qsim (<0,3%). Đây là bước (4) trong §7 — đã xong.

---

## 7. Risks & next steps

**Risks:** (1) delay-line dispersion/loss limits real suppression below the ideal — mitigate with
per-harmonic amplitude/phase trim (path to >65 dB). (2) SD's inverted ghost + one-cycle dead time
must be handled in firmware. (3) SPAD C_j and V_BR spread part-to-part → per-unit bias calibration.

**Next steps:** (1) ✅ schematic captured + KiCad-importable netlist + BOM (§4a). (2) ✅ **PCB
layout** — done headless via `pcbnew` Python (§4b, `layout.py`): 50 Ω microstrip + the length-tuned
0.80 ns delay meander + ground pour + gerbers. Remaining for fab: real vendor footprints + final RF
trim/impedance verification (bench). (3) tighten SPAD device params against the chosen part's
datasheet + bench measurement. (4) ✅ **FPGA gate-veto + ghost-reject + LVDS timestamp** firmware
written & Verilator-validated (§6a, `hardware/bob_fpga/`). (5) ✅ **Alice gain-switch laser-driver
board** — ngspice driver + a two-rate-equation laser model give a ~21 ps, phase-randomised optical
pulse; qsim-closed (`hardware/alice_laser_driver/`, its own README).

> **Giải thích — rủi ro & việc tiếp:** rủi ro chính: dây trễ thực có tổn hao/tán sắc làm khử kém hơn
> lý tưởng (khắc phục bằng tinh chỉnh từng hài). Việc tiếp: siết thông số SPAD theo datasheet thật →
> vẽ **schematic + layout PCB trong KiCad** (trở kháng 50 Ω, dây trễ là đường mạch/coax tuned) → viết
> **firmware FPGA** (khóa cổng sau click, loại bóng ma, đóng dấu thời gian) → rồi sang board của Alice.

---

## 8. References

- Z. L. Yuan et al., "High speed single photon detection in the near infrared," *Appl. Phys.
  Lett.* **91**, 041114 (2007) — self-differencing.
- L. C. Comandar et al., "Gigahertz-gated InGaAs/InP single-photon detector with detection
  efficiency exceeding 55 % at 1550 nm," arXiv:1412.1586 (2014).
- Compact SD InGaAs/InP module, 30 % PDE / 2.4 % afterpulse / 8×10⁻⁷ dark per gate,
  arXiv:2401.02625 (2024).
- A. Tosi et al., InGaAs/InP SPAD characterisation, arXiv:1105.3760 — **also the afterpulse
  reference behind `qsim`'s impairment model** (consistent provenance across sim and hardware).
- Rusca et al., *Appl. Phys. Lett.* **112**, 171104 (2018) — the finite-key bound qsim reproduces.
