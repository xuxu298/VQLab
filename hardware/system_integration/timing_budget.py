"""End-to-end timing budget for the QKD link — the system-integration layer.

No single subsystem sim sees this. H3 (Alice) gives the source timing jitter; H1 (Bob) gives the
detector jitter; H2 (firmware) gives the gate/dead-time. But the *link* adds two contributors that
only exist once the pieces are wired through one shared clock over a real fiber:

  1. **Clock-distribution jitter** — Alice and Bob share a clock recovered over the 1310 nm sync
     channel; the recovery PLL adds timing noise that neither end's bench sim contains.
  2. **Chromatic dispersion** — the ONLY distance-dependent term. A gain-switched DFB is
     transient-chirped, so its (broad) spectrum spreads in time over the fiber. This is invisible
     at the component bench but grows linearly with span.

Combining all of them in quadrature against the detection slot reveals a SECOND, independent reach
limit — dispersion/timing-limited — alongside the loss-limited reach the finite-key already bounds.
That two-limit picture is the whole point of integrating the subsystems: the link can be fine on
loss yet timing-limited (or vice versa), and only the assembled budget tells you which bites first.

Convention: FWHM-class timing figures combined in quadrature (the standard timing-budget
approximation); the per-term provenance is in-line. Numbers tie to the catalog (Alice/Bob) and to
ITU-T G.652 (fiber). Distance is the independent variable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# --- link parameters (provenance in comments; all datasheet/standard-class) -----------------
FIBER_D_PS_NM_KM = 17.0      # SMF G.652 chromatic dispersion @1550 nm (ITU-T G.652: ~16-18)
SOURCE_LINEWIDTH_NM = 0.15   # *effective* spectral width of a gain-switched DFB — transient chirp
                             # broadens it far beyond the CW linewidth (~0.1-0.3 nm typical). The
                             # dominant lever on dispersion; documented as a design parameter.
CLOCK_SYNC_JITTER_PS = 15.0  # recovered-clock jitter over the 1310 nm sync channel (OCXO +
                             # clock-recovery PLL; few-tens-of-ps class)
TDC_JITTER_PS = 10.0         # time-to-digital converter / time-tagger single-shot jitter (Bob BE)
BUDGET_FRACTION = 0.25       # working rule: total timing error must stay < 25% of the gate period
                             # (matches the configurator's jitter design-rule; ISI/gate-overlap)


@dataclass
class TimingContribution:
    name: str
    ps: float                 # FWHM-class timing spread (ps)
    distance_dependent: bool
    note: str


@dataclass
class TimingBudget:
    distance_km: float
    gate_rate_hz: float
    contributions: list[TimingContribution]

    @property
    def total_ps(self) -> float:
        """Quadrature sum of all contributions (independent random timing terms)."""
        return math.sqrt(sum(c.ps ** 2 for c in self.contributions))

    @property
    def gate_period_ps(self) -> float:
        return 1e12 / self.gate_rate_hz

    @property
    def budget_ps(self) -> float:
        return BUDGET_FRACTION * self.gate_period_ps

    @property
    def margin(self) -> float:
        """total / budget. <1 = within budget; >1 = timing-limited."""
        return self.total_ps / self.budget_ps

    @property
    def within_budget(self) -> bool:
        return self.total_ps <= self.budget_ps

    @property
    def fixed_ps(self) -> float:
        """Quadrature sum of the distance-INDEPENDENT terms (the timing floor)."""
        return math.sqrt(sum(c.ps ** 2 for c in self.contributions if not c.distance_dependent))


def dispersion_ps(distance_km: float, linewidth_nm: float = SOURCE_LINEWIDTH_NM,
                  d_ps_nm_km: float = FIBER_D_PS_NM_KM) -> float:
    """Pulse spread from chromatic dispersion: Δt = D · L · Δλ."""
    return d_ps_nm_km * distance_km * linewidth_nm


def build_budget(distance_km: float, gate_rate_hz: float, source_jitter_ps: float,
                 detector_jitter_ps: float, clock_jitter_ps: float = CLOCK_SYNC_JITTER_PS,
                 tdc_jitter_ps: float = TDC_JITTER_PS,
                 linewidth_nm: float = SOURCE_LINEWIDTH_NM) -> TimingBudget:
    """Assemble the full end-to-end timing budget at one span (single source of truth)."""
    contributions = [
        TimingContribution("Alice source (gain-switch)", source_jitter_ps, False,
                           "H3 designed transmitter jitter"),
        TimingContribution("Bob detector (SPAD)", detector_jitter_ps, False,
                           "H1 detector timing jitter (FWHM)"),
        TimingContribution("Clock distribution (1310 nm)", clock_jitter_ps, False,
                           "shared-clock recovery PLL"),
        TimingContribution("TDC / time-tagger", tdc_jitter_ps, False, "Bob readout electronics"),
        TimingContribution("Chromatic dispersion (fiber)",
                           dispersion_ps(distance_km, linewidth_nm), True,
                           f"{FIBER_D_PS_NM_KM:g} ps/nm/km x {distance_km:g} km x {linewidth_nm:g} nm"),
    ]
    return TimingBudget(distance_km, gate_rate_hz, contributions)


def dispersion_limited_reach_km(gate_rate_hz: float, fixed_jitter_ps: float,
                                linewidth_nm: float = SOURCE_LINEWIDTH_NM,
                                d_ps_nm_km: float = FIBER_D_PS_NM_KM) -> float:
    """Span at which total timing error hits the 25%-gate-period budget (the timing reach limit).

    budget^2 = fixed^2 + (D·L·Δλ)^2  =>  L = sqrt(budget^2 - fixed^2) / (D·Δλ).
    Returns 0 if the fixed floor alone already exceeds the budget.
    """
    budget = BUDGET_FRACTION * 1e12 / gate_rate_hz
    if budget <= fixed_jitter_ps:
        return 0.0
    return math.sqrt(budget ** 2 - fixed_jitter_ps ** 2) / (d_ps_nm_km * linewidth_nm)


def timing_efficiency(total_ps: float, slot_ps: float) -> float:
    """Gate-overlap detection efficiency: fraction of the photon arrival-time Gaussian
    (sigma = FWHM / 2.355) that lands inside the centred detection slot of width `slot_ps`.

    = erf( (slot/2) / (sigma·√2) ). ~1 when timing << slot; rolls off as they become comparable.
    A standard, conservative way to fold timing spread into an efficiency penalty.
    """
    sigma = total_ps / 2.35482
    if sigma <= 0:
        return 1.0
    return math.erf((slot_ps / 2.0) / (sigma * math.sqrt(2.0)))
