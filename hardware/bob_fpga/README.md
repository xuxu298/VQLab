# Bob detector FPGA firmware (H2)

The digital half of the H1 self-differencing gating board (`../bob_gating_board/`, docs/03). The
analog front-end (SPAD → 180° hybrid → LNA → fast comparator) turns each gate period into at most
one LVDS event; this firmware does the three jobs that front-end cannot, per gate, in real time.

## What it does

| Job | Why | RTL |
|---|---|---|
| **Ghost-reject** | Self-differencing leaves an *inverted copy* of every real avalanche exactly one gate period later (docs/03 §3). | The gate immediately after an accepted click is always vetoed — independent of the afterpulse setting. |
| **Gate-veto** | Afterpulsing: trapped charges re-trigger the SPAD for a few ns after a click. | `veto_cycles` gates are held off after each accepted click (= the detector dead time). |
| **Timestamp** | Bob must time-tag each detection to sift/align against Alice. | Each accepted photon is tagged with the running gate index and strobed out (`event_valid`/`event_ts`); serialized back over LVDS on the board. |

`bob_gating.v` is synthesizable, single-clock (the gate clock), non-paralyzable (clicks during a
hold-off do **not** extend it), with telemetry counters (`n_accepted`, `n_ghost`, `n_afterpulse`).

## Run it

```bash
sudo apt install verilator                  # one-time (Verilator >= 4.0)
python3 hardware/bob_fpga/sim.py            # build + run the self-checking testbench
python3 -m hardware.bob_fpga.validate_with_qsim   # close the hardware<->sim loop
```

- **`sim_main.cpp`** — a Verilator C++ testbench driving the RTL through 7 named scenarios (single
  photon → one timestamp; ghost rejected; afterpulse hold-off + exact re-arm timing; ghost rejected
  even with `veto_cycles=0`; disarm ignores clicks and freezes the counter; saturated throughput
  = 1/(veto+1); monotonic timestamps). Exits non-zero on any failure. **26 checks, 0 failed.**
- **`validate_with_qsim.py`** — derives `veto_cycles = round(tau_dead · gate_rate)` from the qsim
  detector (`ingaas_sd`: 3 ns, 1.25 GHz → **4 gates**), checks the firmware-enforced dead time
  (3.2 ns) matches `tau_dead` within one gate, then co-simulates a random comparator stream and
  confirms the measured accepted rate follows the dead-time law `m = r/(1 + r·veto)` to <0.3%.
  This is the same hardware↔sim closure as H1's ngspice loop — the firmware and the simulator
  agree on the same physical dead time.

`tests/test_firmware.py` runs both under `pytest` (auto-skipped where Verilator is absent).

## Next

PCB/IO constraints + LVDS SERDES wrapper for the target FPGA, multi-channel instantiation (×2 for
the two detectors, docs/03 §1), and a clock-domain-crossing FIFO to the host/TDC — the layout-time
steps. The behavioural core (gate-veto + ghost-reject + timestamp) is what this milestone pins down.
