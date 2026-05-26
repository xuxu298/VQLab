"""QC-hardware device blocks — a noisy 2-qubit Bell-state generator on the kernel.

QubitRegister -> BellCircuit -> BellReadout, wired into a DeviceGraph and driven by the SAME
MultiRateScheduler as QKD/sensing. Demonstrates the genuinely-new M4 capabilities running on
the unchanged kernel: a multi-qubit density matrix flowing on QUANTUM_STATE, an ENTANGLING
gate (CNOT), and a CONTROL-driven gate schedule with a slowly-drifting calibration error
(reusing PhaseDriftOU) that the readout tracks — the QC analog of QKD's drifting AMZI phase.
"""
from __future__ import annotations

import numpy as np

from ..core.block import Block, SimContext, Timescale
from ..core.impairments import PhaseDriftOU
from ..core.signals import SignalType
from .backend import DensityMatrixBackend, cnot, embed, H, rz
from .signals import QubitState

BELL = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)   # (|00> + |11>)/sqrt(2)


class QubitRegister(Block):
    """Initialise an n-qubit register in |0...0> each tick (out: QUANTUM_STATE)."""

    def __init__(self, name: str, backend: DensityMatrixBackend):
        super().__init__(name, Timescale.STATIC)
        self.backend = backend
        self.ports_out = {"q": SignalType.QUANTUM_STATE}

    def process(self, batch, ctx: SimContext) -> QubitState:
        shots = int(ctx.shared.get("pulses", 0))
        return QubitState(n_qubits=self.backend.n, rho=self.backend.zero_state(), shots=shots)


class BellCircuit(Block):
    """Prepare a Bell pair: H on q0 then CNOT(0,1), each gate followed by T1/T2 relaxation.

    A slow coherent over-rotation `eps` (an RZ phase miscalibration on q0) drifts as an OU
    process, so the prepared-state fidelity wanders over time — the bench knob a calibration
    loop would null out. Exercises the CONTROL/slow-drift path with a multi-qubit state.
    """

    def __init__(self, name: str, backend: DensityMatrixBackend, *, t_gate: float,
                 miscal_sigma: float = 0.0, miscal_theta: float = 20.0):
        super().__init__(name, Timescale.SLOW_DRIFT)
        self.backend = backend
        self.t_gate = float(t_gate)
        self.noise = backend.relax_channel_matrix(t_gate)
        self.drift = PhaseDriftOU(theta=miscal_theta, sigma=miscal_sigma)
        self.eps = 0.0
        self.n = backend.n
        self.h0 = embed(H, 0, self.n)
        self.cx = cnot(0, 1, self.n)
        self.ports_in = {"q": SignalType.QUANTUM_STATE}
        self.ports_out = {"q": SignalType.QUANTUM_STATE}

    def step(self, ctx: SimContext) -> None:
        self.eps = self.drift.step(ctx.dt, ctx.rng)
        ctx.shared["miscal_eps"] = self.eps

    def process(self, batch: QubitState, ctx: SimContext) -> QubitState:
        be = self.backend
        rho = batch.rho
        rho = be.apply_channel(be.apply_unitary(rho, self.h0), self.noise)
        if self.eps:                                   # coherent phase miscalibration on q0
            rho = be.apply_unitary(rho, embed(rz(self.eps), 0, self.n))
        rho = be.apply_channel(be.apply_unitary(rho, self.cx), self.noise)
        batch.rho = rho
        return batch

    def reset(self) -> None:
        self.drift.reset()
        self.eps = 0.0


class BellReadout(Block):
    """Read out the Bell pair: accumulate the exact state fidelity to (|00>+|11>)/sqrt2 and a
    shot-sampled 'parity success' P(00)+P(11) (the measurable correlation), per tick.

    Teaching point kept deliberately: the slow RZ *phase* miscalibration degrades the exact
    fidelity (it kills the off-diagonal coherence) but is INVISIBLE to computational-basis
    parity P(00)+P(11) — a coherent phase error needs rotated-basis readout / tomography to
    see. So fidelity tracks the drift while parity does not; that contrast is the lesson."""

    def __init__(self, name: str, backend: DensityMatrixBackend):
        super().__init__(name, Timescale.PER_EVENT)
        self.backend = backend
        self.ports_in = {"q": SignalType.QUANTUM_STATE}
        self.reset()

    def reset(self) -> None:
        self.n_ticks = 0
        self.sum_fid = 0.0
        self.shots_total = 0
        self.parity_hits = 0

    def process(self, batch: QubitState, ctx: SimContext) -> QubitState:
        be = self.backend
        fid = be.fidelity_pure(batch.rho, BELL)
        self.sum_fid += fid
        self.n_ticks += 1

        probs = be.populations(batch.rho)             # [P00, P01, P10, P11]
        probs = np.clip(probs, 0, None)
        probs = probs / probs.sum()
        if batch.shots > 0:
            outcomes = ctx.rng.choice(len(probs), size=batch.shots, p=probs)
            self.parity_hits += int(np.count_nonzero((outcomes == 0) | (outcomes == 3)))
            self.shots_total += batch.shots
        ctx.shared["metrics"] = {"fidelity_tick": fid}
        return batch

    def stats(self) -> tuple[float, float]:
        """(mean exact Bell fidelity, shot-estimated parity-success P(00)+P(11))."""
        mean_fid = self.sum_fid / self.n_ticks if self.n_ticks else 0.0
        parity = self.parity_hits / self.shots_total if self.shots_total else float("nan")
        return mean_fid, parity
