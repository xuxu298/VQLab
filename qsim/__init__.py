"""qsim — open-source, device-level quantum-technology simulation platform.

A domain-agnostic kernel (graph + typed signals + multi-rate scheduler + pluggable
quantum-state backends + impairment/calibration API) with per-domain plugins. As of M4 the
same kernel hosts four devices across three domains with no kernel edits: QKD (decoy-BB84,
finite-key validated vs Rusca 2018), QRNG (beam-splitter RNG), sensing (atomic magnetometer,
Bloch backend + sensitivity validated vs the Budker-Romalis projection-noise limit), and QC
hardware (multi-qubit density-matrix/Lindblad, gate fidelity validated vs randomized
benchmarking).

See docs/02_simulator_kernel_spec.md for the architecture this implements.
"""

__version__ = "0.0.5-M4"


def load_scenario_plugins() -> list[str]:
    """Import the shipped plugins' scenario runners so their `kind`s are registered, and
    return the available kinds. The kernel never imports plugins itself (spec §10), so this
    convenience lives at the top level, not in qsim.core."""
    from . import qchw, qkd, qrng, sensing  # noqa: F401  (import side effect: register runners)
    from .qkd import scenarios as _qkd_scen  # noqa: F401
    from .qrng import scenarios as _qrng_scen  # noqa: F401
    from .sensing import scenarios as _sensing_scen  # noqa: F401
    from .qchw import scenarios as _qchw_scen  # noqa: F401
    from .core.scenario import available_kinds

    return available_kinds()
