# System integration — end-to-end QKD link

Assembles the separately-designed subsystems (Alice **H3** + fiber + Bob **H1/H2** + finite-key)
into **one link** with a single timing/clock budget as the spine. See
[`docs/04_system_integration.md`](../../docs/04_system_integration.md) for the full story.

The point: two timing contributors exist **only once the pieces share one clock over a real fiber**
— clock-distribution jitter (1310 nm sync) and chromatic dispersion (distance-dependent) — so they
appear in no single subsystem bench. Folding them in reveals a **second, independent reach limit**
(dispersion/timing) alongside the loss-limited reach the finite-key already bounds.

```bash
python -m hardware.system_integration.integrate            # text table + figure
python -m hardware.system_integration.integrate --no-plot  # text only
pytest tests/test_system_integration.py -q
```

- `timing_budget.py` — pure timing-budget model (RSS of Alice/Bob/clock/TDC + `D·L·Δλ` dispersion;
  25%-gate-period rule; dispersion-limited reach; gate-overlap efficiency). Provenance in-line.
- `integrate.py` — combines the budget with the **validated** configurator (loss/QBER/SKR) across
  distance; prints the Phase-1 loop-closed summary; renders `demos/figures/system_integration.png`.
