# QKD Link — System Integration (End-to-End Timing Budget)

**Version:** v0.1 · **Scope:** assemble Alice (H3) + fiber + Bob (H1/H2) + finite-key into one
link, with a single timing/clock budget as the spine. **Code:** `hardware/system_integration/`
(`timing_budget.py`, `integrate.py`). **Figure:** `demos/figures/system_integration.png`.

> 📖 **Cách đọc:** mỗi phần có bảng/giải thích kỹ thuật (EN) + khối **"Giải thích"** (VI) ngay sau.
> Tài liệu này là *bước tích hợp* — nó không thêm vật lý mới ở mức linh kiện, mà ghép các subsystem
> đã thiết kế (H1/H2/H3 + finite-key) thành **một tuyến** và hỏi: *cả tuyến có khép không, và cái gì
> giới hạn tầm trước?*

---

## 0. Why an integration step at all

Each subsystem was designed and qsim-closed on its own bench: **H3** (Alice gain-switch driver) gives
the source timing jitter; **H1** (Bob self-differencing front-end) gives the detector jitter; **H2**
(firmware) gives the gate/dead-time; the **finite-key** model (Rusca 2018) turns counts into a proven
secret-key rate. But two effects exist **only once the pieces share one clock over a real fiber**, so
no single bench sim contains them:

1. **Clock-distribution jitter** — Alice and Bob run off one clock recovered over the 1310 nm sync
   channel; the recovery PLL adds timing noise.
2. **Chromatic dispersion** — the **only distance-dependent** timing term. A gain-switched DFB is
   transient-chirped (broad spectrum), so its pulse spreads in time along the fiber.

Folding everything into one budget reveals a **second, independent reach limit** —
dispersion/timing-limited — sitting next to the loss-limited reach the finite-key already bounds.

> **Giải thích:** từng khối (Alice, Bob, firmware, finite-key) đã được mô phỏng & kiểm chứng *riêng*.
> Nhưng khi ghép chúng lại qua **một đồng hồ chung** và **một sợi quang thật**, xuất hiện 2 thứ mà
> không bench đơn lẻ nào thấy: (1) **jitter phân phối clock** (đồng bộ qua kênh 1310 nm), và (2)
> **tán sắc sợi quang** — thứ duy nhất *tăng theo khoảng cách*. Ghép tất cả vào một "ngân sách thời
> gian" cho ra một phát hiện: tuyến có **hai giới hạn tầm độc lập** — do *suy hao* và do *tán sắc/timing*
> — và cần biết cái nào "cắn" trước.

---

## 1. The end-to-end timing budget

All terms are FWHM-class timing spreads, combined in quadrature (the standard timing-budget
approximation). Numbers tie to the catalog (Alice/Bob subsystems) and ITU-T G.652 (fiber).

| Contribution | Value | Distance-dep.? | Source |
|---|---|---|---|
| Alice source (gain-switch) | 20 ps | no | H3 designed transmitter |
| Bob detector (InGaAs SPAD) | 90 ps | no | H1 detector jitter (FWHM) |
| Clock distribution (1310 nm sync) | 15 ps | no | shared-clock recovery PLL |
| TDC / time-tagger | 10 ps | no | Bob readout electronics |
| **Chromatic dispersion (fiber)** | `D · L · Δλ` | **yes** | G.652: D≈17 ps/(nm·km), Δλ≈0.15 nm |

- **Fixed floor** (distance-independent terms, RSS): √(20²+90²+15²+10²) ≈ **94 ps**.
- **Dispersion** at span *L*: 17 · *L* · 0.15 = **2.55·*L* ps** (≈64 ps at 25 km, ≈128 ps at 50 km).
- **Total** = √(floor² + dispersion²).
- **Working rule** (same as the configurator): total must stay **< 25% of the gate period**
  (= 200 ps at 1.25 GHz → 800 ps period). This is a conservative ISI / gate-overlap guard.

> **Giải thích — vì sao Δλ≈0.15 nm là tham số then chốt:** laser DFB chạy gain-switch bị *chirp*
> quá độ → phổ rộng hơn nhiều so với linewidth lúc phát liên tục (CW). Phổ càng rộng, tán sắc làm
> xung *giãn theo thời gian* càng nhiều trên cùng chiều dài sợi. Đây là đòn bẩy lớn nhất lên tán sắc;
> để là tham số thiết kế (có thể giảm bằng nguồn phổ hẹp hơn / bù tán sắc). Đầu dò SPAD (90 ps) là
> đóng góp tĩnh lớn nhất; tán sắc là đóng góp *động* duy nhất.

---

## 2. Two independent reach limits

Sweeping the span at **1.25 GHz, InGaAs-SD, gain-switched DFB** (the H1/H3 reference config):

| Span | Loss | QBER | Secret-key rate | Total jitter | Margin (×budget) |
|---|---|---|---|---|---|
| 10 km | 5.5 dB | 1.05 % | 14.9 Mbps | 97 ps | 0.49× |
| **25 km (Phase 1)** | **8.5 dB** | **1.05 %** | **7.9 Mbps** | **114 ps** | **0.57×** |
| 50 km | 13.5 dB | 1.06 % | 2.6 Mbps | 158 ps | 0.79× |
| 75 km | 18.5 dB | 1.08 % | 0.83 Mbps | 213 ps | 1.07× |
| 100 km | 23.5 dB | 1.15 % | 0.26 Mbps | 272 ps | 1.36× |

- **Loss-limited reach** — the finite-key SKR rolls off with attenuation (InGaAs class ~60–80 km;
  SNSPD goes further). This is the limit the validated configurator already bounds.
- **Timing-limited reach** — total jitter crosses the 25%-gate budget at **~69 km** (1.25 GHz),
  where chromatic dispersion has grown enough to threaten the gate window.
- At **Phase-1 25 km** both have large margin: timing is **0.57×** budget (~2.8× headroom) and the
  link is comfortably **loss-dominated** — QBER 1.05 %, SKR ~7.9 Mbps, feasible. The gate-overlap
  detection-efficiency penalty from timing is negligible (η_timing ≈ 100 %) across the whole metro
  range; the 25% rule trips well before efficiency does.

> **Giải thích:** ở 1.25 GHz, **hai giới hạn tầm gần nhau (~60–80 km)** — nên ở metro 25 km cả hai
> đều dư rất nhiều. Nếu kéo tuyến dài ra (long-haul) sẽ đụng cả suy hao *lẫn* tán sắc. Hệ quả thiết kế:
> tăng nhịp cổng (→ tăng SKR) làm chu kỳ cổng ngắn lại nên **siết ngân sách timing** → giới hạn tán sắc
> tiến gần hơn; metro Phase-1 chọn 25 km là điểm *an toàn trên cả hai trục*. Muốn vươn xa hơn: nguồn
> phổ hẹp/bù tán sắc (đẩy giới hạn timing) **và** đầu dò tốt hơn như SNSPD (đẩy giới hạn suy hao).

---

## 3. The assembled link (one shared clock)

```
  shared clock (OCXO @ Alice) ── 1310 nm sync ──► clock recovery @ Bob
         │                                              │
         ▼ (low-jitter trigger)                         ▼ (gate phase-locked)
  Alice: gain-switch 21 ps pulse ─ decoy ─ encode ─ →μ  ══ 25 km SMF (dispersion) ══►  Bob: AMZI ─ DWDM ─ SD-gated SPAD ─ TDC tag
                                                                                              │
                                  sift ─ LDPC EC ─ privacy amp ─ Wegman-Carter auth ─ finite-key ─► proven key → ETSI QKD-014 → KMS
```

The integration check (`integrate.py`) confirms the assembled link **closes at Phase-1**: every
subsystem's output is a valid input to the next, the shared-clock timing budget sits within the gate
window with headroom, and the finite-key turns the resulting counts into a positive proven SKR.
This is the same hardware↔sim loop-closure discipline as H1/H2/H3, now at the **whole-link** level.

> **Giải thích:** điểm mấu chốt của tích hợp là **một đồng hồ chung**: Alice phát theo OCXO, Bob khôi
> phục đúng nhịp đó qua kênh 1310 nm và khóa pha cổng. Chỉ khi tổng jitter (Alice + Bob + clock + TDC +
> tán sắc) **nhỏ hơn nhiều so với cửa sổ cổng** thì photon mới rơi đúng cổng → tuyến mới chạy. Script
> `integrate.py` xác nhận điều đó ở Phase-1 và in "INTEGRATED OK" — đúng kỷ luật khép vòng HW↔sim như
> H1/H2/H3, nhưng ở mức **cả tuyến**.

---

## 4. Honest scope

- The timing terms are **FWHM-class datasheet/standard figures combined in quadrature** — a standard
  budget approximation, not a full statistical-optics pulse-propagation simulation. Tighten against
  measured component data before a production claim.
- `Δλ ≈ 0.15 nm` for the gain-switched DFB is a **documented design parameter** (chirp-broadened);
  the dispersion reach scales inversely with it.
- The loss-limited SKR/QBER comes from the **validated** finite-key configurator unchanged; this
  layer only **adds** the timing dimension on top — it does not modify the core model.
- The gate-overlap efficiency (`timing_efficiency`) is a conservative centred-Gaussian/erf model of
  the slot overlap; it is reported, not used to inflate the SKR.

> **Giải thích:** đây là **ngân sách kỹ thuật** ở mức quadrature (đủ để ra quyết định thiết kế &
> giới hạn tầm), chưa phải mô phỏng lan truyền xung đầy đủ. Lớp tích hợp **không sửa** model finite-key
> đã kiểm chứng — chỉ chồng thêm trục thời gian. Các con số nên siết lại với số đo linh kiện thật trước
> khi tuyên bố production.
