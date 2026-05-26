"""qsim configurator — the multi-domain reference-design configurator (headless core).

A high-level knob set (per domain) drives, from one source of truth, the behavioural
simulation, the reference hardware BOM + board parameters, and design-rule checks. One GUI
renders any domain because the report shape is uniform (see report.ConfigReport).

Domains plug in via a registry (mirrors the kernel's plugin pattern): QKD link (decoy-BB84),
atomic-magnetometer sensing, and few-qubit QC hardware. NOT a schematic editor (that would
reinvent KiCad); the detailed circuit lives in the expert reference design (docs/03, hardware/)
+ KiCad — the configurator selects and parametrises it.

    from qsim.configurator import configure, list_domains, domain_schema
    rep = configure("qkd", {"detector": "ingaas_sd", "distance_km": 25})
    print(rep.format())
"""
from .report import BomItem, ConfigReport, Metric
from .registry import configure, domain_schema, list_domains, sweep_of
from .spec import DeviceSpec
from . import domains  # noqa: F401  (import side effect: register qkd/sensing/qchw)

__all__ = ["configure", "list_domains", "domain_schema", "sweep_of",
           "ConfigReport", "Metric", "BomItem", "DeviceSpec"]
