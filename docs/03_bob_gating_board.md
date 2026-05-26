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

## 7. Risks & next steps

**Risks:** (1) delay-line dispersion/loss limits real suppression below the ideal — mitigate with
per-harmonic amplitude/phase trim (path to >65 dB). (2) SD's inverted ghost + one-cycle dead time
must be handled in firmware. (3) SPAD C_j and V_BR spread part-to-part → per-unit bias calibration.

**Next steps:** (1) tighten SPAD device params against the chosen part's datasheet + bench
measurement. (2) Capture this topology as a **KiCad schematic** + PCB layout (controlled-impedance
50 Ω, the delay line as a tuned trace/coax). (3) Write the **FPGA gate-veto + ghost-reject + LVDS
timestamp** firmware (Verilog, sim in Verilator). (4) Then the Alice timing/laser-driver board.

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
