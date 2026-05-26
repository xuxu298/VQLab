"""Domain-agnostic configuration report — the common output shape across all domains.

QKD, sensing and QC-hardware each compute different physics, but the *container* is uniform:
a set of metrics, a BOM grouped by side, derived board parameters, and design-rule findings.
This is what lets one GUI render any domain generically.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# design-rule severity levels
PASS, INFO, WARN, FAIL = "PASS", "INFO", "WARN", "FAIL"


@dataclass
class Metric:
    key: str
    label: str
    value: float
    unit: str = ""
    display: str = ""           # preformatted string for the UI (falls back to value+unit)

    def shown(self) -> str:
        return self.display or f"{self.value:g} {self.unit}".strip()


@dataclass
class BomItem:
    ref: str
    part: str
    side: str
    qty: int
    line_cost_usd: float


@dataclass
class ConfigReport:
    domain: str
    name: str
    metrics: list[Metric]
    bom: list[BomItem]
    cost_by_side: dict
    bom_total_usd: float
    board_params: dict
    rules: list[tuple[str, str]]
    feasible: bool
    headline_keys: list[str] = field(default_factory=list)   # which metrics to feature

    def m(self, key: str) -> float:
        return next(x.value for x in self.metrics if x.key == key)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "name": self.name,
            "metrics": [{"key": x.key, "label": x.label, "value": x.value,
                         "unit": x.unit, "display": x.shown()} for x in self.metrics],
            "headline_keys": self.headline_keys,
            "bom": [{"ref": it.ref, "part": it.part, "side": it.side,
                     "qty": it.qty, "line_cost_usd": it.line_cost_usd} for it in self.bom],
            "cost_by_side": self.cost_by_side,
            "bom_total_usd": self.bom_total_usd,
            "board_params": {k: str(v) for k, v in self.board_params.items()},
            "rules": [{"level": lv, "msg": msg} for lv, msg in self.rules],
            "feasible": self.feasible,
        }

    def format(self) -> str:
        L = [f"=== [{self.domain}] {self.name} ==="]
        for x in self.metrics:
            L.append(f"    {x.label:<26}: {x.shown()}")
        L.append("  -- BOM --")
        for side, c in self.cost_by_side.items():
            L.append(f"    {side+' subtotal':<26}: ${c:,.0f}")
        L.append(f"    {'TOTAL':<26}: ${self.bom_total_usd:,.0f}")
        L.append("  -- rules --")
        for lv, msg in self.rules:
            L.append(f"    [{lv}] {msg}")
        L.append(f"  => {'FEASIBLE' if self.feasible else 'NOT FEASIBLE'}")
        return "\n".join(L)


def assemble_bom(lines, *, n_channels: int = 1) -> tuple[list[BomItem], dict, float]:
    """Turn catalog BomLine objects into BomItems (qty scaled) + per-side cost + total."""
    items: list[BomItem] = []
    by_side: dict[str, float] = {}
    for ln in lines:
        qty = ln.qty_per_channel * n_channels + ln.qty_per_board
        if qty == 0:
            continue
        cost = qty * ln.unit_cost_usd
        items.append(BomItem(ln.ref, ln.part, ln.side, qty, cost))
        by_side[ln.side] = by_side.get(ln.side, 0.0) + cost
    return items, by_side, sum(by_side.values())


def feasible(rules: list[tuple[str, str]]) -> bool:
    return not any(lv == FAIL for lv, _ in rules)
