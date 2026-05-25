"""Probes — attach to record time-series of any quantity (spec §9)."""
from __future__ import annotations


class TimeSeriesProbe:
    def __init__(self, name: str):
        self.name = name
        self.t: list[float] = []
        self.y: list[float] = []

    def record(self, t: float, y: float) -> None:
        self.t.append(t)
        self.y.append(y)

    def reset(self) -> None:
        self.t.clear()
        self.y.clear()
