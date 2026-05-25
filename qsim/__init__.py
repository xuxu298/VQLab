"""qsim — open-source, device-level quantum-technology simulation platform.

M0 milestone: a runnable proof-of-concept of the kernel (graph + typed signals +
multi-rate scheduler + Fock backend + impairment API) driving one QKD vertical slice
(faint pulse -> fiber -> gated InGaAs detector with realistic impairments + slow AMZI
phase drift -> QBER accumulated by batches).

See docs/02_simulator_kernel_spec.md for the architecture this implements.
"""

__version__ = "0.0.1-M0"
