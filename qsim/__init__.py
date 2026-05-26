"""qsim — open-source, device-level quantum-technology simulation platform.

M0 milestone: a runnable proof-of-concept of the kernel (graph + typed signals +
multi-rate scheduler + Fock backend + impairment API) driving one QKD vertical slice
(faint pulse -> fiber -> gated InGaAs detector with realistic impairments + slow AMZI
phase drift -> QBER accumulated by batches).

See docs/02_simulator_kernel_spec.md for the architecture this implements.
"""

__version__ = "0.0.3-M2"


def load_scenario_plugins() -> list[str]:
    """Import the shipped plugins' scenario runners so their `kind`s are registered, and
    return the available kinds. The kernel never imports plugins itself (spec §10), so this
    convenience lives at the top level, not in qsim.core."""
    from . import qkd, qrng  # noqa: F401  (import side effect: register runners)
    from .qkd import scenarios as _qkd_scen  # noqa: F401
    from .qrng import scenarios as _qrng_scen  # noqa: F401
    from .core.scenario import available_kinds

    return available_kinds()
