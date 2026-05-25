"""MultiRateScheduler — the hard core (spec §6).

Couples a SLOW stepped layer (drift, control loops; ms-s) with a FAST batched layer
(pulse-rate physics aggregated statistically). Each slow tick:
  1. call step() on every block -> update quasi-static state (phase drift, PID, ...)
  2. push ONE representative PulseBatch through the block chain via process()
  3. record instantaneous metrics; accumulate across ticks.

This is the laptop-tractable approximation of "run the device for seconds-to-hours":
the slow state modulates the fast batch, and statistics accumulate over batches.
"""
from __future__ import annotations

import numpy as np

from .block import SimContext
from .graph import DeviceGraph


class MultiRateScheduler:
    def __init__(self, graph: DeviceGraph):
        self.graph = graph
        self.order = graph.topo_order()

    def run(
        self,
        *,
        n_ticks: int,
        dt_slow: float,
        pulses_per_tick: int,
        rng: np.random.Generator,
        record: bool = True,
    ) -> list[dict]:
        """Run n_ticks of the slow clock, each driving one fast batch.

        Returns a list of per-tick records (when record=True). Cumulative metrics live
        on the blocks themselves (e.g. the detector's running QBER).
        """
        records: list[dict] = []
        t = 0.0
        for _ in range(n_ticks):
            ctx = SimContext(t=t, dt=dt_slow, rng=rng, shared={"pulses": pulses_per_tick})

            # 1) slow layer: advance drift / control / quasi-static params
            for b in self.order:
                b.step(ctx)

            # 2) fast layer: one representative batch through the chain
            batch = None
            for b in self.order:
                batch = b.process(batch, ctx)

            # 3) record instantaneous state
            if record:
                rec = {"t": t}
                rec.update(ctx.shared.get("metrics", {}))
                rec["e_opt"] = ctx.shared.get("e_opt")
                rec["phase_resid"] = ctx.shared.get("phase_resid")
                records.append(rec)
            t += dt_slow
        return records

    def reset(self) -> None:
        for b in self.order:
            b.reset()
