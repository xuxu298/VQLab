"""Calibration profiles with provenance (spec §7).

Every parameter carries WHERE its value came from (datasheet / paper DOI / measured) so
a simulated device is auditable and a result can be traced to its assumptions. This is
what separates a credible 'digital twin' from a toy.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CalParam:
    value: float
    unit: str = ""
    source: str = "unspecified"   # e.g. "datasheet:MPD-PDM-IR", "doi:10.1103/...", "measured:2026-..."
    note: str = ""


class CalibrationProfile:
    """A named bag of CalParams loaded from YAML."""

    def __init__(self, name: str, params: dict[str, CalParam]):
        self.name = name
        self.params = params

    def value(self, key: str) -> float:
        return self.params[key].value

    def source(self, key: str) -> str:
        return self.params[key].source

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CalibrationProfile":
        data = yaml.safe_load(Path(path).read_text())
        params = {
            k: CalParam(
                value=float(v["value"]),
                unit=v.get("unit", ""),
                source=v.get("source", "unspecified"),
                note=v.get("note", ""),
            )
            for k, v in data["params"].items()
        }
        return cls(name=data.get("name", Path(path).stem), params=params)
