"""qsim — open-source, device-level quantum-technology simulation platform.

A domain-agnostic kernel (graph + typed signals + multi-rate scheduler + pluggable
quantum-state backends + impairment/calibration API) with per-domain plugins. As of M3 the
same kernel hosts three domains with no kernel edits: QKD (decoy-BB84, finite-key validated
vs Rusca 2018), QRNG (beam-splitter RNG), and sensing (atomic magnetometer, Bloch backend +
sensitivity validated vs the Budker-Romalis projection-noise limit).

See docs/02_simulator_kernel_spec.md for the architecture this implements.
"""

__version__ = "0.0.4-M3"


def load_scenario_plugins() -> list[str]:
    """Import the shipped plugins' scenario runners so their `kind`s are registered, and
    return the available kinds. The kernel never imports plugins itself (spec §10), so this
    convenience lives at the top level, not in qsim.core."""
    from . import qkd, qrng, sensing  # noqa: F401  (import side effect: register runners)
    from .qkd import scenarios as _qkd_scen  # noqa: F401
    from .qrng import scenarios as _qrng_scen  # noqa: F401
    from .sensing import scenarios as _sensing_scen  # noqa: F401
    from .core.scenario import available_kinds

    return available_kinds()
