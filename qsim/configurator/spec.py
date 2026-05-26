"""DeviceSpec — the high-level, shareable device specification (the configurator's input).

A small set of physically-meaningful knobs. Everything else (sim parameters, BOM, board
parameters) is *derived* from this by the compiler, so a DeviceSpec is the single source of
truth for a configured device and a one-file shareable artifact (like a scenario, but it
spans both the behavioural sim and the hardware design).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass
class DeviceSpec:
    name: str = "qkd_device"
    protocol: str = "decoy_bb84"          # the only protocol wired so far
    detector: str = "ingaas_sd"           # catalog key: "ingaas_sd" | "snspd"
    n_channels: int = 2                   # Bob detector channels (2 or 4)
    gate_rate_hz: float = 1.25e9          # gating / clock rate
    distance_km: float = 25.0             # metro span
    fiber_alpha_db_km: float = 0.2        # G.652 @ 1550 nm
    bob_insertion_db: float = 3.5         # Bob optics insertion loss (AMZI + filter + conn.)
    e_misalignment: float = 0.01          # intrinsic optical error (AMZI visibility ~98%)
    n_z_block: float = 1e8                # finite-key Z-basis block size
    # optional manual intensities; if None the compiler optimises them
    mu1: float | None = None
    mu2: float | None = None
    notes: str = ""
    meta: dict = field(default_factory=dict)

    # fields that must be numeric even if YAML parsed them as strings (e.g. "1e8":
    # YAML 1.1 only treats an exponent as a float when it carries a sign, so 1.0e8 -> str)
    _FLOAT_FIELDS = ("gate_rate_hz", "distance_km", "fiber_alpha_db_km", "bob_insertion_db",
                     "e_misalignment", "n_z_block", "mu1", "mu2")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DeviceSpec":
        data = yaml.safe_load(Path(path).read_text())
        fields = {f for f in cls.__dataclass_fields__}
        kw = {k: v for k, v in data.items() if k in fields}
        for f in cls._FLOAT_FIELDS:
            if kw.get(f) is not None:
                kw[f] = float(kw[f])
        if "n_channels" in kw:
            kw["n_channels"] = int(kw["n_channels"])
        return cls(**kw)

    def to_yaml(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(asdict(self), sort_keys=False))

    def replace(self, **changes) -> "DeviceSpec":
        """A copy with some knobs changed (the 'turn one knob' operation)."""
        d = asdict(self)
        d.update(changes)
        return DeviceSpec(**d)
