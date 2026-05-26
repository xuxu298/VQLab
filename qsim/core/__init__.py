"""qsim.core — the domain-agnostic kernel.

Nothing in here knows about QKD; domain knowledge lives in plugins (qsim.qkd, ...).
"""

from .signals import SignalType, PulseBatch
from .block import Block, Timescale, SimContext
from .graph import DeviceGraph
from .scheduler import MultiRateScheduler
from .backends import QuantumStateBackend, FockBackend
from .impairments import (
    Impairment,
    FixedEfficiency,
    DarkCount,
    Afterpulsing,
    DeadTime,
    PhaseDriftOU,
)
from .calibration import CalibrationProfile, CalParam
from .probes import TimeSeriesProbe
from .sweep import SweepResult, OptimizeResult, sweep, optimize

__all__ = [
    "SignalType",
    "PulseBatch",
    "Block",
    "Timescale",
    "SimContext",
    "DeviceGraph",
    "MultiRateScheduler",
    "QuantumStateBackend",
    "FockBackend",
    "Impairment",
    "FixedEfficiency",
    "DarkCount",
    "Afterpulsing",
    "DeadTime",
    "PhaseDriftOU",
    "CalibrationProfile",
    "CalParam",
    "TimeSeriesProbe",
    "SweepResult",
    "OptimizeResult",
    "sweep",
    "optimize",
]
