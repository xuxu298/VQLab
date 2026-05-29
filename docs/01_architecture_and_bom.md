# QKD Device — System Architecture & BOM

**Version:** v0.2 (draft + giải thích) · **Date:** 2026-05-25
**Scope:** Phase 1 — metro fiber link, decoy-state BB84, 1550 nm, time-bin/phase encoding
**Toolchain:** open-source (KiCad, ngspice, FreeCAD, gdsfactory/sax, GHDL/Verilator)

> ⚠️ **Part numbers below are representative/credible but MUST be datasheet-verified.** Some
> vendors have renamed or been acquired (e.g., iXblue → Exail; Princeton Lightwave defunct).
> Treat this as the v1 architecture skeleton; the next step is web-verifying long-lead parts.

> 📖 **Cách đọc file này:** mỗi phần có (1) bảng spec kỹ thuật tiếng Anh — đây là bản dùng để
> đặt hàng linh kiện; và (2) khối **"Giải thích"** tiếng Việt ngay sau đó — nói rõ phần
> đó/linh kiện đó **làm gì, tại sao cần, nếu hỏng thì sao**. Đọc khối Giải thích trước cho dễ hình dung.

---

## Bức tranh tổng thể (đọc cái này trước)

QKD (Quantum Key Distribution) = hai bên **Alice** (phát) và **Bob** (thu) tạo ra một **khóa bí mật
chung** bằng cách gửi từng photon đơn lẻ qua sợi quang. Vật lý lượng tử đảm bảo: nếu có kẻ nghe lén
(Eve) chen vào đo trộm photon, nó **chắc chắn để lại dấu vết** (tăng tỷ lệ lỗi QBER), nên Alice–Bob
phát hiện được và bỏ khóa đó đi. Khác với mã hóa toán học thông thường, an toàn ở đây dựa trên **định
luật vật lý**, không bị máy tính lượng tử tương lai bẻ.

Thiết bị của ta gồm 3 mảng:
1. **Alice** — máy phát: tạo xung laser, mã hóa bit vào photon, hạ xuống mức ~1 photon, bắn đi.
2. **Bob** — máy thu: nhận photon, giải mã, đếm bằng đầu dò đơn photon, gắn nhãn thời gian.
3. **Hậu xử lý + đồng bộ + kênh classical** — hai bên "nói chuyện" qua Ethernet thường để sàng lọc,
   sửa lỗi, chưng cất ra khóa cuối, rồi giao khóa cho hệ thống mã hóa sử dụng nó.

---

## 0. Design targets (Phase 1)

| Parameter | Target | Notes |
|---|---|---|
| Protocol | Decoy-state BB84 (1-decoy, Rusca 2018) | Mature, finite-key proven |
| Encoding | Time-bin / phase (AMZI) | Robust to fiber polarization drift |
| Wavelength | 1550.12 nm (ITU DWDM C-band) | 0.2 dB/km, standard fiber infra reuse |
| Fiber | SMF G.652, dedicated dark fiber (Phase 1) | WDM coexistence = Phase 2 roadmap |
| Distance | 25 km target, 50 km envelope | Metro, no trusted-node needed |
| Source intensity μ | ~0.4–0.5 photons/pulse | Optimize in design-validation sim |
| Clock | Start 100 MHz → 1 GHz | FPGA-paced |
| Detector (P1) | InGaAs/InP gated SPAD, TEC −40 °C | Upgrade path → SNSPD |
| Key rate (target) | tens–hundreds kbps @25 km (InGaAs) | Mbps-class after SNSPD upgrade |
| Standards ref | ETSI GS QKD 014 (key delivery), ITU-T Y.3800 | Standards compliance / KMS integration |

> **Giải thích từng thông số:**
> - **Protocol — Decoy-state BB84:** BB84 là giao thức QKD kinh điển (1984). "Decoy-state" = trộn
>   thêm các xung *mồi* cường độ khác nhau để bắt bài kiểu tấn công "tách số photon" (PNS). Bản
>   *1-decoy (Rusca 2018)* chỉ cần 1 mức mồi nên đơn giản phần cứng mà vẫn chứng minh được an toàn
>   với **khóa hữu hạn** (số xung thực tế, không phải vô hạn lý thuyết).
> - **Encoding — time-bin/phase:** ghi bit vào **thời điểm** hoặc **pha** của xung photon, thay vì
>   phân cực. Lý do: sợi quang làm xoay phân cực lung tung theo nhiệt/rung → mã phân cực dễ hỏng;
>   time-bin/phase bền hơn nhiều trên hạ tầng sợi quang thật.
> - **Wavelength — 1550.12 nm:** nằm trong cửa sổ C-band, **suy hao thấp nhất** của sợi quang
>   (~0.2 dB/km) và trùng đúng lưới bước sóng DWDM viễn thông → tái dùng hạ tầng sẵn có.
> - **Fiber — G.652 dark fiber:** sợi đơn-mode tiêu chuẩn phổ biến nhất. Phase 1 thuê **sợi tối**
>   riêng (chưa ghép chung với lưu lượng data) để giảm nhiễu; ghép chung (WDM) để dành Phase 2.
> - **Distance 25–50 km:** tầm "metro" (nội đô) — đủ ngắn để **không cần trusted node** (điểm trung
>   chuyển phải tin tưởng), nên bài toán bảo mật gọn hơn.
> - **μ ~0.4–0.5 photon/xung:** cường độ trung bình cực thấp để mỗi xung **xấp xỉ một photon**. Đây
>   là cốt lõi bảo mật — Eve không thể "copy" 1 photon (định lý no-cloning).
> - **Clock 100 MHz → 1 GHz:** nhịp bắn xung. Bắt đầu chậm cho dễ debug, tăng dần để **tăng tốc độ
>   tạo khóa**.
> - **Detector InGaAs SPAD, TEC −40 °C:** đầu dò bắt được từng photon ở 1550 nm, làm lạnh để bớt
>   "đếm tối" (đếm nhầm do nhiệt). Sau này nâng cấp lên SNSPD xịn hơn.
> - **Key rate:** tốc độ sinh **khóa bí mật** thực tế (bps). InGaAs cho vài chục–vài trăm kbps;
>   lên SNSPD đạt cỡ Mbps.
> - **Standards (ETSI/ITU):** tuân chuẩn quốc tế để khóa **cắm thẳng** vào hệ quản lý khóa (KMS)
>   qua API REST chuẩn.

---

## 1. System block diagram

```
 ALICE (Quantum Transmitter)                              BOB (Quantum Receiver)
 ┌──────────────────────────────────────┐               ┌──────────────────────────────────────┐
 │ DFB laser 1550nm ─(gain-switch)       │   QUANTUM     │  PolCtrl → AMZI(matched) → DWDM filt  │
 │   → IM (decoy) → Phase/Time-bin enc   │   CHANNEL     │     → [DETECTOR MODULE]               │
 │   → VOA(→single photon) → ISO → out ──┼──── SMF ──────┼──→  (InGaAs SPAD | SNSPD)             │
 │            ▲ monitor PD               │   (dark fiber)│            │ discriminated pulse       │
 │   ┌────────┴─────────┐                │               │     ┌──────┴──────┐                   │
 │   │ FPGA timing+pattern│←QRNG          │               │     │ TDC/time-tag │                  │
 │   │ laser drv · mod drv│               │   SYNC CH     │     │ FPGA timestamp+sync+phase-lock│  │
 │   │ bias ctrl · TEC    │───sync laser──┼──── SMF ──────┼──→  └──────┬──────┘                   │
 │   └────────────────────┘               │  (1310nm)     │            │                          │
 └──────────────────────────────────────┘               └────────────┼──────────────────────────┘
                                                                      │
                CLASSICAL CHANNEL (Ethernet) ── sift / LDPC EC / privacy amp / auth ──┐
                                                                                      ▼
                                                          ETSI QKD-014 API → KMS / encryptor
```

> **Giải thích sơ đồ (đi theo đường photon):**
> 1. **Alice** bật laser DFB ở chế độ gain-switch → ra xung ánh sáng cực ngắn.
> 2. Qua **IM** (điều chế cường độ): chọn mức tín hiệu hay mức *mồi* (decoy).
> 3. Qua **mã hóa pha/time-bin**: ghi bit + basis (do QRNG sinh ngẫu nhiên) vào photon.
> 4. Qua **VOA**: hạ công suất xuống ~đơn photon; qua **ISO** (cách ly) rồi bắn vào sợi quang.
> 5. Photon chạy qua **kênh lượng tử** (sợi tối) tới **Bob**.
> 6. Bob: **PolCtrl** chỉnh phân cực → **AMZI** giải mã pha → **lọc DWDM** lọc nhiễu →
>    **đầu dò** bắt photon → ra xung số.
> 7. **TDC + FPGA** của Bob gắn nhãn thời gian, đồng bộ đồng hồ với Alice (nhờ **kênh sync 1310 nm**).
> 8. Hai bên trao đổi qua **kênh classical** (Ethernet thường): **sàng lọc → sửa lỗi LDPC →
>    khuếch đại bảo mật → xác thực** → ra **khóa chung**.
> 9. Khóa được giao qua **API ETSI QKD-014** cho **KMS/encryptor** dùng để mã hóa dữ liệu.

---

## 2. Interface contract (the boundaries that make it modular)

Defining clean interfaces now is what lets us swap detectors and scale clock later
without redesigning everything.

- **Optical channel:** SMF G.652, FC/PC (or FC/APC) connectors, 1550.12 nm quantum + 1310 nm sync.
- **Detector module boundary (CRITICAL for InGaAs→SNSPD upgrade):**
  - IN: single-mode fiber (FC/PC)
  - IN: gate clock (LVDS) — *used by InGaAs gating; SNSPD ignores it (free-running)*
  - OUT: discriminated detection event (LVDS/LVPECL digital pulse)
  - => FPGA, TDC, sifting, and all post-processing are **detector-agnostic**.
- **Alice↔Bob classical:** Gigabit Ethernet (SFP), authenticated (Wegman–Carter).
- **Key output:** ETSI GS QKD 014 REST API to a KMS.

> **Giải thích — tại sao phần "interface" này quan trọng:**
> Đây là các **đường biên (chân cắm) chuẩn hóa** giữa các module. Nếu định nghĩa rõ từ đầu thì sau
> này ta **thay ruột mà không phải đập đi làm lại**. Ví dụ điển hình: khối đầu dò (detector) có đúng
> 3 chân — *vào: sợi quang + xung nhịp cổng; ra: xung số khi bắt được photon*. Vì giao diện cố định,
> nên khi nâng cấp từ **InGaAs (rẻ) sang SNSPD (xịn)**, toàn bộ FPGA/TDC/hậu xử lý **giữ nguyên** —
> chỉ rút module cũ cắm module mới — thiết kế không bị khóa cứng vào một lựa chọn phần cứng.

---

## 3. ALICE — Quantum Transmitter

> **Giải thích — Alice là gì:** đây là **máy phát**, đặt ở một đầu tuyến. Nhiệm vụ: biến tín hiệu
> số (bit + basis ngẫu nhiên) thành **từng photon đơn** đã mã hóa, rồi bắn qua sợi. Gồm 2 mảng:
> *chuỗi quang* (3.1 — các linh kiện ánh sáng) và *điện tử điều khiển* (3.2 — board mạch + FPGA),
> cộng *firmware* (3.3 — phần mềm chạy trong FPGA).

### 3.1 Optical chain (BOM)

| # | Function | Representative part | Key spec | ~Cost (USD) | Notes |
|---|---|---|---|---|---|
| A1 | Pulsed source | Eblana Photonics EP1550-DM (discrete-mode DFB), gain-switched | low chirp/jitter, 1550 nm | 0.3–1k (device) | gain-switch via fast driver |
| A2 | Intensity mod (decoy) | EOSPACE / Exail LiNbO₃ MZM | extinction >30 dB, >10 GHz | 3–8k | high ER critical for security |
| A3 | Phase / time-bin enc | Exail MPZ-LN-10 phase mod **or** Kylia asymmetric MZI | Vπ low, stable ΔL | 3–10k | AMZI must match Bob's |
| A4 | Variable attenuator | OZ Optics DA-100 / Thorlabs V1550A (calibrated) | 0–50 dB, fine step | 1–3k | sets μ to single-photon level |
| A5 | Optical isolator | Thorlabs IO-H-1550 (or inline) | >30 dB isolation | 0.3–0.6k | block back-reflection / Trojan |
| A6 | Monitor PD | Thorlabs FGA01FC (InGaAs PIN) | for power/decoy calibration | 0.2k | feedback to bias loop |

> **Giải thích từng linh kiện quang của Alice:**
> - **A1 — Nguồn phát xung (laser DFB gain-switched):** "trái tim" tạo photon. Laser DFB phát đúng
>   1550 nm; chạy chế độ *gain-switch* (giật dòng bật/tắt cực nhanh) để ra **xung ánh sáng cực ngắn,
>   sạch, ít chirp/jitter** — định thời chính xác là bắt buộc cho time-bin.
> - **A2 — Điều chế cường độ / decoy (MZM LiNbO₃):** "công tắc ánh sáng" tốc độ cao. Dùng để đặt mỗi
>   xung vào mức *tín hiệu* hay *mồi*. **Tỷ số tắt/mở (ER) > 30 dB là sống còn**: ánh sáng rò khi
>   đáng lẽ phải "tắt" = lỗ hổng bảo mật.
> - **A3 — Mã hóa pha / time-bin:** ghi **bit** vào photon, bằng bộ điều chế pha hoặc giao thoa kế
>   bất đối xứng (AMZI). **ΔL (chênh lệch quang trình) phải khớp y hệt AMZI của Bob**, nếu lệch thì
>   Bob không giải mã được.
> - **A4 — Suy hao biến thiên (VOA):** "núm vặn độ sáng". Hạ công suất xung xuống mức trung bình
>   ~0.5 photon/xung — **chính bước này biến ánh sáng cổ điển thành chế độ lượng tử**.
> - **A5 — Cách ly quang (isolator):** "van một chiều" cho ánh sáng. Chặn phản xạ ngược làm nhiễu
>   laser, và chặn tấn công **Trojan-horse** (Eve bắn ánh sáng ngược vào Alice để dò trạng thái).
> - **A6 — Photodiode giám sát:** "đồng hồ đo" công suất ra, để **hiệu chuẩn** mức μ và mức mồi cho
>   chuẩn; phản hồi về vòng điều khiển bias để giữ ổn định.

### 3.2 Electronics (PCB — design in KiCad, analog sim in ngspice)

| # | Function | Representative part | Key spec | ~Cost | Notes |
|---|---|---|---|---|---|
| AE1 | Timing/pattern FPGA | AMD Kintex-7 (Digilent Genesys 2) **or** Lattice ECP5 (open flow) | GTX/SERDES, sub-ns timing | 1–3k | see §7 FPGA-flow note |
| AE2 | Laser driver | gain-switch: fast comparator + RF stage (iC-Haus iC-HG class) | <500 ps pulse | custom + 0.1k | design in ngspice |
| AE3 | Modulator RF driver | broadband RF amp (e.g., SHF / Mini-Circuits) | match Vπ, GHz BW | 0.5–2k | drives A2/A3 |
| AE4 | MZM bias controller | Exail MBC-DG **or** FPGA+DAC dither-lock | auto bias-drift lock | 1–2k (or custom) | prevents ER drift |
| AE5 | QRNG | ID Quantique Quantis (chip/module) **or** vacuum-fluctuation design | true random, high rate | 1–3k | feeds bit+basis choice |
| AE6 | TEC controller (laser) | ADI ADN8834 / Maxim MAX1968 | ±0.01 °C | 0.05k | wavelength stability |
| AE7 | Clock / power | OCXO ref + clean DC rails | low jitter | 0.3k | jitter → timing budget |

> **Giải thích từng khối điện tử của Alice:**
> - **AE1 — FPGA định thời/pattern:** "bộ não số". Phát nhịp chủ, sinh chuỗi bit/basis, và **điều
>   phối mọi tín hiệu thời gian ở mức dưới nano-giây** (đồng bộ laser, modulator).
> - **AE2 — Driver laser:** mạch tạo **xung dòng cực nhanh (<500 ps)** để gain-switch A1. Thiết kế &
>   mô phỏng analog trong ngspice.
> - **AE3 — Driver RF cho modulator:** khuếch đại tín hiệu lên đủ biên độ (điện áp Vπ) và đủ băng
>   thông GHz để **lái A2/A3** chuyển trạng thái kịp tốc độ xung.
> - **AE4 — Bộ điều khiển bias MZM:** modulator LiNbO₃ **bị trôi điểm làm việc theo nhiệt/thời gian**.
>   Khối này tự dò và khóa lại (dither-lock) để giữ ER ổn định — không có nó, bảo mật suy giảm dần.
> - **AE5 — QRNG (nguồn ngẫu nhiên lượng tử):** quyết định **bit và basis** cho mỗi xung. Phải là
>   ngẫu nhiên **thật** (từ vật lý lượng t), vì nếu đoán được chuỗi này thì toàn bộ khóa mất an toàn.
> - **AE6 — Điều khiển nhiệt laser (TEC):** giữ laser ở nhiệt độ cố định **±0.01 °C** để bước sóng
>   không trôi (bước sóng trôi → lệch khỏi AMZI/filter).
> - **AE7 — Clock/nguồn:** dao động chuẩn OCXO **jitter thấp** + nguồn DC sạch. Jitter đồng hồ ăn
>   trực tiếp vào **ngân sách định thời** — jitter cao thì time-bin nhòe, QBER tăng.

### 3.3 Firmware (FPGA gateware — Verilog/VHDL, sim GHDL/Verilator)

- Pulse-timing engine (gain-switch trigger + modulator pattern aligned)
- Decoy/state sequencer (drives IM intensity level + phase/time-bin per random input)
- QRNG sampling + buffering
- Sync frame generation (drives sync laser)

> **Giải thích — firmware Alice làm gì:** đây là phần mềm chạy bên trong FPGA (AE1), viết bằng
> Verilog/VHDL. Bốn nhiệm vụ: (1) **engine định thời xung** — căn chính xác khi nào kích laser và
> khi nào modulator đổi trạng thái; (2) **sequencer decoy/state** — với mỗi bit ngẫu nhiên, ra lệnh
> cho IM chọn mức cường độ và cho bộ mã hóa chọn pha/time-bin; (3) **lấy mẫu & đệm QRNG** — đọc số
> ngẫu nhiên đủ nhanh; (4) **sinh khung sync** — phát tín hiệu cho laser sync để Bob bám đồng hồ.

---

## 4. BOB — Quantum Receiver

> **Giải thích — Bob là gì:** đây là **máy thu** ở đầu kia. Nhiệm vụ: nhận photon yếu ớt từ sợi,
> giải mã ngược lại, **đếm từng photon** và ghi lại **thời điểm** nó tới. Phần khó nhất của cả hệ
> nằm ở đây: đầu dò đơn photon và giữ giao thoa kế ổn định.

### 4.1 Optical chain (BOM)

| # | Function | Representative part | Key spec | ~Cost | Notes |
|---|---|---|---|---|---|
| B1 | Polarization controller | OZ Optics EPC (electronic) / Thorlabs MPC | active stabilization | 1–3k | also needed before SNSPD |
| B2 | Decoding AMZI | Kylia asymmetric MZI (matched to A3) | phase-stabilized (thermal/piezo) | 5–10k | ΔL must equal Alice's |
| B3 | DWDM bandpass filter | AC Photonics 100 GHz filter | reject Raman/out-of-band | 0.3–0.8k | matters more in Phase-2 WDM |

> **Giải thích từng linh kiện quang của Bob:**
> - **B1 — Bộ điều khiển phân cực:** sợi quang làm xoay phân cực photon một cách ngẫu nhiên theo
>   nhiệt/rung. Khối này **chủ động bù lại** để AMZI (và sau này SNSPD vốn nhạy phân cực) hoạt động đúng.
> - **B2 — AMZI giải mã:** giao thoa kế bất đối xứng, **khớp đúng ΔL với A3 của Alice**. Nó biến
>   chênh lệch *pha* của photon thành chênh lệch *đường ra* → đo được bit. Phải **ổn định pha** liên
>   tục bằng nhiệt/piezo, nếu không kết quả trôi.
> - **B3 — Lọc băng DWDM:** lọc hẹp ~100 GHz quanh 1550 nm, **loại bỏ ánh sáng tạp** (tán xạ Raman,
>   ngoài băng). Phase 1 (sợi tối) ít tạp nên đỡ quan trọng; **Phase 2 ghép chung sợi với data** thì
>   khối này cực kỳ then chốt.

### 4.2 Detector module — Phase 1 (InGaAs) **[swappable unit]**

| # | Function | Representative part | Key spec | ~Cost | Notes |
|---|---|---|---|---|---|
| BD1 | SPAD | MPD InGaAs/InP module **or** bare SPAD (Wooriro/AdTech) | η ~20–25 %, λ 1550 | 5–15k/ch | 2–4 ch for BB84 bases |
| BD2 | Gating + quenching | custom (sine-gate + self-differencing, Toshiba/Yuan style) | GHz gating, afterpulse mgmt | custom | design in ngspice |
| BD3 | SPAD TEC | ADI ADN8834 + Peltier | −40 °C | 0.1k | dark-count control |

> **Giải thích — khối đầu dò InGaAs (Phase 1, có thể tháo rời):**
> - **BD1 — SPAD (đầu dò quang thác đơn photon):** linh kiện **bắt được từng photon** ở 1550 nm.
>   Hiệu suất η ~20–25% (cứ ~4–5 photon mới bắt được 1). Cần **2–4 kênh** để đo các basis của BB84.
> - **BD2 — Mạch gating + quenching:** **phần khó và khác biệt nhất** của dự án. "Gating" = chỉ mở
>   cổng SPAD đúng khoảnh khắc photon dự kiến tới (giảm mạnh đếm tối). "Quenching" = dập nhanh dòng
>   thác sau khi bắt được, và quản lý **afterpulse** (xung dội giả). Tự thiết kế, mô phỏng trong ngspice.
> - **BD3 — TEC làm lạnh SPAD:** ép SPAD xuống **−40 °C** để giảm "đếm tối" (đếm nhầm do nhiệt sinh
>   hạt mang điện). Lạnh hơn = nhiễu thấp hơn = QBER tốt hơn.

### 4.3 Detector module — Upgrade (SNSPD) **[drop-in replacement of §4.2]**

| # | Function | Representative part | Key spec | ~Cost | Notes |
|---|---|---|---|---|---|
| BD1' | SNSPD system | Single Quantum Eos / IDQ ID281 / Photon Spot | η 85–95 %, jitter 15–50 ps | 150–400k | includes closed-cycle cryostat |
| BD2' | Bias + RF readout | µA bias source + cryo/RT amplifier | low-noise | (incl.) | replaces gating board |
| BD3' | + Pol controller | (B1 reused/added) | align to nanowire axis | — | SNSPD polarization-sensitive |

> **Giải thích — khối nâng cấp SNSPD (cắm thay thẳng cho §4.2):**
> - **BD1' — Hệ SNSPD (dây nano siêu dẫn):** đầu dò đỉnh cao — **hiệu suất 85–95%**, jitter cực thấp
>   (15–50 ps). Đổi lại phải có **cryostat** làm lạnh xuống ~1–3 K và giá rất cao. Nhảy vọt cả **tốc
>   độ khóa lẫn tầm xa**.
> - **BD2' — Nguồn bias + đọc RF:** SNSPD cần dòng bias cỡ µA + khuếch đại tín hiệu RF; **thay cho
>   board gating/quenching** của InGaAs.
> - **BD3' — Bộ điều khiển phân cực:** SNSPD **nhạy phân cực**, nên cần căn phân cực photon theo trục
>   dây nano (tái dùng/bổ sung B1).

### 4.4 Detection electronics (kept across upgrade)

| # | Function | Representative part | Key spec | ~Cost | Notes |
|---|---|---|---|---|---|
| BE1 | TDC / time-tagger | Swabian Time Tagger 20/Ultra **or** FPGA carry-chain TDC | ps resolution | 5–10k (or custom) | threshold/timing programmable |
| BE2 | FPGA | same family as Alice | timestamp, sync recovery, AMZI phase-lock | 1–3k | detector-agnostic |
| BE3 | AMZI phase-lock | DAC → thermal/piezo driver on B2 | closed loop | 0.2k | keep interferometer at quadrature |

> **Giải thích — điện tử thu (dùng chung cho cả InGaAs lẫn SNSPD):**
> - **BE1 — TDC / time-tagger:** "đồng hồ bấm giờ siêu chính xác" (độ phân giải pico-giây). Mỗi khi
>   đầu dò ra xung, nó **ghi lại thời điểm** → từ đó biết photon rơi vào **khe thời gian/pha nào** = bit gì.
> - **BE2 — FPGA thu:** gắn nhãn thời gian, **khôi phục đồng bộ** với Alice, chạy vòng khóa pha AMZI.
>   Cùng dòng FPGA với Alice và **detector-agnostic** (không cần biết đang dùng InGaAs hay SNSPD).
> - **BE3 — Khóa pha AMZI:** vòng kín — DAC lái bộ gia nhiệt/piezo trên B2 để **giữ giao thoa kế đứng
>   yên tại điểm làm việc (quadrature)**, chống trôi do nhiệt độ.

### 4.5 Firmware

- Gate-timing generation (InGaAs) — bypassable for SNSPD
- Detection event timestamping + sync recovery from sync channel
- AMZI phase-stabilization control loop
- Sifting interface to post-processing

> **Giải thích — firmware Bob làm gì:** (1) **sinh nhịp cổng** cho InGaAs (bỏ qua khi dùng SNSPD vì
> SNSPD chạy tự do); (2) **đóng dấu thời gian** sự kiện đếm + bám đồng bộ từ kênh sync; (3) **vòng ổn
> định pha AMZI**; (4) **giao diện sàng lọc** đẩy dữ liệu thô sang khối hậu xử lý.

---

## 5. Sync + Classical + Post-processing

| Block | Approach | Notes |
|---|---|---|
| Sync channel | 1310 nm bright pulse + fast PIN + clock recovery (or White Rabbit) | aligns Alice/Bob clocks |
| Classical channel | Gigabit Ethernet over SFP | authenticated |
| Post-processing | sift → LDPC error correction → privacy amp (Toeplitz) → auth (Wegman–Carter) | server or FPGA-offloaded; finite-key Lim 2014 |
| Key delivery | ETSI GS QKD 014 REST API → KMS / encryptor | standard key-delivery interface |

> **Giải thích từng khối:**
> - **Kênh sync (1310 nm):** một bước sóng *khác* mang xung sáng mạnh để Bob **khôi phục đồng hồ** của
>   Alice — hai bên phải khớp thời gian từng pico-giây thì mới biết photon nằm ở khe nào.
> - **Kênh classical (Ethernet):** đường truyền **thường, công khai nhưng có xác thực**. Hai bên dùng
>   nó để bàn bạc xử lý dữ liệu (không truyền khóa qua đây).
> - **Hậu xử lý (4 bước):** **Sift** = chỉ giữ các xung mà Alice/Bob *tình cờ dùng cùng basis*.
>   **LDPC** = sửa các bit sai do nhiễu sợi. **Privacy amplification (Toeplitz)** = băm khóa ngắn lại
>   để **ép phần thông tin Eve có thể đã nghe lén về 0**. **Auth (Wegman–Carter)** = xác thực để Eve
>   không giả mạo được kênh classical. (Chứng minh an toàn khóa hữu hạn theo Lim 2014.)
> - **Key delivery (ETSI QKD-014):** giao khóa thành phẩm cho **KMS/encryptor** qua API REST chuẩn.

---

## 6. Detector upgrade path summary (InGaAs → SNSPD)

| Item | InGaAs (Phase 1) | SNSPD (upgrade) | Impact |
|---|---|---|---|
| Drive board | gating + quenching + HV bias | µA bias + RF readout | **replaced** |
| Cooling | TEC −40 °C (1U) | cryostat 0.8–2.8 K (rack) | **added**, standard rack DC |
| Polarization | insensitive | sensitive → needs PolCtrl | **added** |
| η / jitter / dark | 20 %, 100–300 ps, higher | 85–95 %, 15–50 ps, lower | **improves** key rate + reach |
| Optics-pre-detector | — | — | **unchanged** (+PolCtrl) |
| TDC / FPGA / post-proc | — | — | **unchanged** (re-tune params) |
| Protocol / security | decoy-BB84 | decoy-BB84 | **unchanged** (note: diff. side-channels; MDI-QKD removes them, future phase) |

> **Giải thích — bảng này nói gì:** nó liệt kê **đúng những thứ thay đổi khi nâng cấp đầu dò**, để
> chứng minh phần lớn hệ thống **giữ nguyên**. Phải *thay* board lái và *thêm* làm lạnh sâu + điều
> khiển phân cực; bù lại **hiệu suất/jitter/nhiễu cải thiện mạnh** → khóa nhanh hơn, đi xa hơn. Quang
> học phía trước, TDC, FPGA, hậu xử lý, giao thức — **không đổi** (chỉ tinh chỉnh tham số). Đây chính
> là minh chứng cho thiết kế module hóa ở §2.

---

## 7. Open-tool mapping per subsystem

| Domain | Open tool | Produces |
|---|---|---|
| Schematic + PCB + 3D board | **KiCad** | schematics, layout, 3D board view, BOM |
| Analog circuit sim | **ngspice / LTspice** | laser driver, gating/quenching SPICE results |
| FPGA HDL simulation | **GHDL / Verilator** | testbench waveforms (vendor-agnostic) |
| FPGA synthesis | **yosys + nextpnr** (Lattice ECP5) *or* Vivado free (Xilinx 7-series) | bitstream — see note |
| Photonic system sim | **gdsfactory + sax / simphony** | QBER, visibility, extinction-ratio modeling |
| 3D mechanical assembly | **FreeCAD** | enclosure, fiber routing, "plug-component" 3D assembly |
| Design-validation (key rate) | Python (decoy-BB84, finite-key) | SKR-vs-distance, QBER budget — *validation only* |

> **Giải thích — công cụ mã nguồn mở cho từng mảng thiết kế:** bảng này map mỗi mảng thiết kế với
> một phần mềm miễn phí và *sản phẩm* nó tạo ra. **KiCad** vẽ schematic + layout PCB + xem board 3D.
> **ngspice** mô phỏng mạch analog (driver laser, gating). **GHDL/Verilator** mô phỏng logic FPGA
> trước khi nạp. **yosys+nextpnr / Vivado** tổng hợp ra bitstream nạp vào FPGA. **gdsfactory+sax** mô
> phỏng hệ quang (QBER, visibility, ER). **FreeCAD** dựng vỏ máy + đi dây sợi quang. **Python** kiểm
> chứng tốc độ khóa theo khoảng cách — *chỉ để validate thiết kế, không phải sản phẩm chính*.

> **FPGA flow note:** HDL *simulation* is fully open (GHDL/Verilator) regardless of vendor.
> For *synthesis*, the fully-FOSS flow (yosys+nextpnr) targets **Lattice ECP5** well — but for
> GHz SERDES timing, **Xilinx 7-series + free Vivado** (free, not FOSS) is the pragmatic choice.
> Decide once we lock the clock rate.

---

## 8. Rough cost summary (order-of-magnitude, per side)

| Configuration | Optics | Electronics | Detector | Approx total |
|---|---|---|---|---|
| Phase 1 (InGaAs, 2-ch) | ~15–35k | ~5–12k | ~10–30k | **~30–80k / link** |
| Upgrade (SNSPD) | +1–3k (PolCtrl) | — | +150–400k | **+150–400k** |

(Excludes labor, fiber lease, and one-time NRE for custom boards.)

> **Giải thích — bảng chi phí (ước lượng độ lớn, mỗi đầu tuyến):** một tuyến QKD cần **2 đầu** (Alice
> + Bob). Phase 1 dùng InGaAs: khoảng **30–80k USD/đầu**, trong đó đắt nhất là *modulator quang* và
> *đầu dò*. Nâng cấp SNSPD đội thêm **150–400k** chủ yếu do hệ làm lạnh cryostat. Con số này **chưa**
> tính công, thuê sợi, và chi phí làm board custom một lần (NRE).

---

## 9. Open questions / risks / next steps

**Open questions — RESOLVED 2026-05-26 in [`03_bob_gating_board.md`](03_bob_gating_board.md) §1:**
1. ✅ Detector channels — **2** (one-way phase/time-bin BB84: 1 AMZI + 2 port detectors; Z from time-slot, X from port). 4 = marginal Phase-1 benefit.
2. ✅ Sync strategy — **dedicated 1310 nm optical sync, CWDM-combined onto the same dark fiber** (avoids a second lease; clock-recovery too photon-starved, White Rabbit unneeded at metro).
3. ✅ Phase-1 span — **25 km assumed** (10–50 km envelope); exact span set at deployment, qsim sweep re-points trivially.

**Key risks:**
- LiNbO₃ modulator bias drift (mitigate: auto-bias controller AE4).
- AMZI phase stability over temperature (mitigate: active phase-lock BE3 + thermal enclosure).
- InGaAs afterpulsing limiting count rate (mitigate: gating + dead time; or jump to SNSPD).
- Long-lead/expensive parts (modulators, SPAD/SNSPD) — verify availability early.

**Immediate next steps:**
1. ✅ First subsystem designed — **Bob gating/quenching board** ([`03_bob_gating_board.md`](03_bob_gating_board.md)): self-differencing front-end, **ngspice-simulated** gate-transient cancellation (34 dB, avalanche discriminable), **qsim-validated** (QBER 1 %, ~8 Mbps @25 km).
2. Next: capture H1 as a **KiCad schematic + PCB** (50 Ω controlled-impedance, tuned delay line); write the **FPGA gate-veto/ghost-reject/timestamp firmware** (Verilog + Verilator).
3. Then the **Alice timing/laser-driver board** (gain-switch <500 ps, ngspice).
4. Web-verify the remaining long-lead optics (A2 modulator, A3/B2 AMZI) for the BOM.

> **Giải thích — phần này để làm gì:** tổng hợp **3 câu hỏi chưa chốt** (số kênh đầu dò, cách đồng bộ,
> khoảng cách demo — đều ảnh hưởng tới thiết kế & chi phí), **4 rủi ro lớn nhất** kèm cách giảm thiểu,
> và **việc cần làm ngay**. Bước kế tiếp quan trọng nhất: *web-verify* các linh kiện đặt hàng lâu
> (modulator, AMZI, SPAD) vì chúng quyết định lịch trình, rồi bắt tay vẽ board khó nhất trước
> (gating/quenching của Bob) để bóc tách rủi ro sớm.
