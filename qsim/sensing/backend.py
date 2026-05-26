"""SpinEnsembleBackend — a Bloch / Lindblad quantum-state backend (spec §3).

This is the M3 generalization proof: a second QuantumStateBackend that has *nothing* to do
with the photon-number `FockBackend`. The kernel never calls a backend directly — only a
domain's blocks do (FockBackend.signal_click_prob is called by QKD/QRNG detector blocks;
the methods here are called by the sensing blocks). So adding a new physics domain needs a
new backend class and new blocks, but zero kernel edits — exactly the claim spec §3 makes.

Physics
-------
The macroscopic spin polarisation S = (Sx, Sy, Sz) of an optically-pumped atomic vapour
obeys the phenomenological Bloch equations

    dS/dt = gamma * (S x B)            # Larmor precession about the field
            - (Sx, Sy, 0) / T2         # transverse (coherence) relaxation
            - (0, 0, Sz - S0) / T1     # longitudinal relaxation toward pumped value S0

For a spin-1/2 this is exactly the Lindblad master equation drho/dt = -i[H, rho] +
dephasing + amplitude-relaxation, rewritten in the Bloch-vector picture
S = (<sigma_x>, <sigma_y>, <sigma_z>) with H = (gamma/2) B.sigma. We integrate the
3-vector form directly: it is transparent (a student can read the master equation off it),
dependency-free (numpy only), and exact-comparable to the closed form. The full density-
matrix form is what M4 (multi-qubit QC hardware) will need; QuTiP becomes worth its weight
there, not here.

Quantum projection noise
------------------------
For N spin-1/2 atoms prepared as a coherent spin state along z (collective spin J = N/2),
the transverse components have variance Var(Jx) = Var(Jy) = J/2 = N/4. The *normalised*
transverse spin Jx/J therefore has standard deviation sqrt(N/4)/(N/2) = 1/sqrt(N). That
1/sqrt(N) angle resolution per readout is the fundamental noise floor of the magnetometer.
"""
from __future__ import annotations

import numpy as np

# Rb-87 ground-state gyromagnetic ratio: Zeeman splitting ~0.70 MHz/G = 7.0 Hz/nT, i.e.
# gamma/2pi = 7.0e9 Hz/T. Used as the default profile constant.
RB87_GAMMA = 2.0 * np.pi * 7.0e9  # rad / (s * T)


class SpinEnsembleBackend:
    """Bloch-vector evolver for an atomic spin ensemble.

    `gamma` is the gyromagnetic ratio in rad/(s*T). State is the 3-vector S (numpy array);
    `B` is the magnetic field 3-vector in tesla. The backend is stateless — it transforms a
    spin vector given a field and a duration, so the same instance serves every cell/cycle.
    """

    name = "bloch"

    def __init__(self, gamma: float = RB87_GAMMA):
        self.gamma = float(gamma)

    # --- the master equation (Bloch form) --------------------------------
    def derivative(self, S: np.ndarray, B: np.ndarray, T1: float, T2: float,
                   S0: float) -> np.ndarray:
        """dS/dt for one spin vector S in field B (the right-hand side integrated below)."""
        precess = self.gamma * np.cross(S, B)
        relax = np.array([S[0] / T2, S[1] / T2, (S[2] - S0) / T1])
        return precess - relax

    def evolve(self, S: np.ndarray, B: np.ndarray, t: float, *, T1: float, T2: float,
               S0: float = 0.0, n_steps: int = 200) -> np.ndarray:
        """Integrate the Bloch equation for total time `t` with fixed-step RK4.

        Fixed-step RK4 is enough because the equation is smooth and linear; `n_steps` is set
        so several steps fall within one Larmor period. Returns the final spin vector.
        """
        S = np.asarray(S, dtype=float).copy()
        B = np.asarray(B, dtype=float)
        h = t / n_steps
        for _ in range(n_steps):
            k1 = self.derivative(S, B, T1, T2, S0)
            k2 = self.derivative(S + 0.5 * h * k1, B, T1, T2, S0)
            k3 = self.derivative(S + 0.5 * h * k2, B, T1, T2, S0)
            k4 = self.derivative(S + h * k3, B, T1, T2, S0)
            S = S + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        return S

    def evolve_analytic(self, S: np.ndarray, Bz: float, t: float, *, T1: float, T2: float,
                        S0: float = 0.0) -> np.ndarray:
        """Closed-form solution for a static field along z — the validation reference.

        With B = (0, 0, Bz) the transverse spin rotates at the Larmor frequency w = gamma*Bz
        and decays as exp(-t/T2); the z-component relaxes toward S0 with time constant T1.
        (Sign of the rotation matches `derivative`: dSx/dt = +gamma*Bz*Sy.)
        """
        w = self.gamma * Bz
        c, s = np.cos(w * t), np.sin(w * t)
        env = np.exp(-t / T2)
        sx = env * (S[0] * c + S[1] * s)
        sy = env * (-S[0] * s + S[1] * c)
        sz = S0 + (S[2] - S0) * np.exp(-t / T1)
        return np.array([sx, sy, sz])

    # --- readout noise ---------------------------------------------------
    @staticmethod
    def projection_noise_std(N: float) -> float:
        """Std of the normalised transverse spin from N-atom quantum projection noise."""
        return 1.0 / np.sqrt(N)
