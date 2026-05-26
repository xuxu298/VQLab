"""Domain registry — the multi-domain dispatch for the configurator.

Each domain (qkd, sensing, qchw) registers a `Domain` describing its knobs (schema + defaults
for the GUI), how to `configure` a knob dict into a ConfigReport, and a `sweep` descriptor that
drives the domain's figure. Mirrors the kernel's plugin pattern: the configurator core knows
nothing domain-specific; domains plug in.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .report import ConfigReport


@dataclass
class Domain:
    name: str                       # key, e.g. "qkd"
    label: str                      # human label
    schema: list[dict]              # knob definitions for the GUI
    defaults: dict                  # default knob values
    configure: Callable[[dict], ConfigReport]
    sweep: dict                     # {knob, label, values, metric, logy} for the figure


DOMAINS: dict[str, Domain] = {}


def register_domain(domain: Domain) -> None:
    DOMAINS[domain.name] = domain


def list_domains() -> list[dict]:
    return [{"name": d.name, "label": d.label} for d in DOMAINS.values()]


def domain_schema(name: str) -> dict:
    d = _get(name)
    return {"name": d.name, "label": d.label, "schema": d.schema, "defaults": d.defaults}


def configure(domain: str, knobs: dict) -> ConfigReport:
    return _get(domain).configure(knobs)


def sweep_of(domain: str) -> dict:
    return _get(domain).sweep


def _get(name: str) -> Domain:
    if name not in DOMAINS:
        raise KeyError(f"unknown domain {name!r}; registered: {sorted(DOMAINS)}")
    return DOMAINS[name]
