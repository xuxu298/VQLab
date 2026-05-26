"""DensityMatrixBackend — a multi-qubit Lindblad backend (spec §3), the third domain.

Everything is a dense complex density matrix rho (2^n x 2^n). This is exact and fully
transparent for the 1-2 qubit device-characterization regime that matters here; a student
can read the master equation straight off `lindblad_propagator`. For large n a sparse/QuTiP
backend would drop in behind the same interface — the kernel never calls a backend directly.

Master equation (Lindblad form):
    drho/dt = -i[H, rho] + sum_k ( L_k rho L_k^dag - 1/2 {L_k^dag L_k, rho} )

We build the Liouvillian superoperator in the column-stacking vectorisation
vec(A X B) = (B^T kron A) vec(X), so the whole evolution for a time t is the single matrix
exponential rho(t) = unvec( expm(Liouvillian * t) vec(rho) ). Relaxation collapse operators
per qubit come from T1 (amplitude damping, L = sqrt(1/T1) |0><1|) and pure dephasing
(L = sqrt(gamma_phi/2) Z with gamma_phi = 1/T2 - 1/(2 T1), so coherences decay at 1/T2).
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import expm

# --- single-qubit operators ------------------------------------------------
I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)
H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
S = np.array([[1, 0], [0, 1j]], dtype=complex)
SIGMA_MINUS = np.array([[0, 1], [0, 0]], dtype=complex)  # |0><1| : lowers |1| -> |0|
PAULIS = {"I": I2, "X": X, "Y": Y, "Z": Z}


def rx(theta: float) -> np.ndarray:
    return np.cos(theta / 2) * I2 - 1j * np.sin(theta / 2) * X


def ry(theta: float) -> np.ndarray:
    return np.cos(theta / 2) * I2 - 1j * np.sin(theta / 2) * Y


def rz(theta: float) -> np.ndarray:
    return np.cos(theta / 2) * I2 - 1j * np.sin(theta / 2) * Z


def _vec(rho: np.ndarray) -> np.ndarray:
    return rho.reshape(-1, order="F")


def _unvec(v: np.ndarray, d: int) -> np.ndarray:
    return v.reshape(d, d, order="F")


def embed(op: np.ndarray, qubit: int, n: int) -> np.ndarray:
    """Embed a single-qubit operator on `qubit` into an n-qubit space (qubit 0 = leftmost)."""
    mats = [op if i == qubit else I2 for i in range(n)]
    out = mats[0]
    for m in mats[1:]:
        out = np.kron(out, m)
    return out


def cnot(control: int, target: int, n: int) -> np.ndarray:
    """CNOT as a full 2^n x 2^n permutation unitary (control, target are qubit indices)."""
    d = 2 ** n
    U = np.zeros((d, d), dtype=complex)
    for k in range(d):
        bits = [(k >> (n - 1 - i)) & 1 for i in range(n)]
        if bits[control]:
            bits[target] ^= 1
        j = sum(b << (n - 1 - i) for i, b in enumerate(bits))
        U[j, k] = 1.0
    return U


class DensityMatrixBackend:
    """n-qubit density-matrix evolver with T1/T2 relaxation."""

    name = "density_matrix"

    def __init__(self, n_qubits: int = 1, *, T1: float = np.inf, T2: float = np.inf):
        self.n = int(n_qubits)
        self.d = 2 ** self.n
        self.T1 = float(T1)
        self.T2 = float(T2)

    # --- states ----------------------------------------------------------
    def zero_state(self) -> np.ndarray:
        rho = np.zeros((self.d, self.d), dtype=complex)
        rho[0, 0] = 1.0
        return rho

    @staticmethod
    def ket_density(psi: np.ndarray) -> np.ndarray:
        psi = psi.astype(complex)
        return np.outer(psi, psi.conj())

    # --- collapse operators ---------------------------------------------
    def collapse_ops(self) -> list[np.ndarray]:
        ops: list[np.ndarray] = []
        gamma_phi = 0.0
        if np.isfinite(self.T2):
            gamma_phi = 1.0 / self.T2 - (1.0 / (2.0 * self.T1) if np.isfinite(self.T1) else 0.0)
            if gamma_phi < -1e-12:
                raise ValueError("require T2 <= 2*T1 for a physical dephasing rate")
            gamma_phi = max(gamma_phi, 0.0)
        for q in range(self.n):
            if np.isfinite(self.T1):
                ops.append(np.sqrt(1.0 / self.T1) * embed(SIGMA_MINUS, q, self.n))
            if gamma_phi > 0.0:
                ops.append(np.sqrt(gamma_phi / 2.0) * embed(Z, q, self.n))
        return ops

    # --- Lindblad evolution ---------------------------------------------
    def liouvillian(self, Hop: np.ndarray | None = None) -> np.ndarray:
        d = self.d
        Id = np.eye(d, dtype=complex)
        L = np.zeros((d * d, d * d), dtype=complex)
        if Hop is not None:
            L += -1j * (np.kron(Id, Hop) - np.kron(Hop.T, Id))
        for c in self.collapse_ops():
            cdc = c.conj().T @ c
            L += np.kron(c.conj(), c) - 0.5 * (np.kron(Id, cdc) + np.kron(cdc.T, Id))
        return L

    def evolve(self, rho: np.ndarray, t: float, Hop: np.ndarray | None = None) -> np.ndarray:
        """Evolve rho for time t under Hamiltonian Hop (default 0) + relaxation."""
        prop = expm(self.liouvillian(Hop) * t)
        return _unvec(prop @ _vec(rho), self.d)

    # --- gates & channels ------------------------------------------------
    @staticmethod
    def apply_unitary(rho: np.ndarray, U: np.ndarray) -> np.ndarray:
        return U @ rho @ U.conj().T

    def relax_channel_matrix(self, t: float) -> np.ndarray:
        """Superoperator (on vec(rho)) for pure relaxation over time t — a reusable channel."""
        return expm(self.liouvillian(None) * t)

    def apply_channel(self, rho: np.ndarray, chan: np.ndarray) -> np.ndarray:
        return _unvec(chan @ _vec(rho), self.d)

    # --- measurement / readout ------------------------------------------
    def prob_zero(self, rho: np.ndarray) -> float:
        """Probability of measuring all qubits in |0...0> (the RB survival observable)."""
        return float(np.real(rho[0, 0]))

    def populations(self, rho: np.ndarray) -> np.ndarray:
        return np.real(np.diag(rho))

    @staticmethod
    def fidelity_pure(rho: np.ndarray, psi: np.ndarray) -> float:
        """State fidelity <psi| rho |psi> to a pure target."""
        return float(np.real(psi.conj() @ rho @ psi))

    # --- exact average gate infidelity of a channel (validation anchor) --
    def avg_gate_infidelity(self, chan: np.ndarray) -> float:
        """1 - F_avg of a single-qubit channel given as a vec-superoperator.

        Single qubit (d=2): F_avg = (3 + sum_{P in X,Y,Z} (1/2) Tr(P Lambda(P))) / 6, i.e.
        F_avg = (3 + R_xx + R_yy + R_zz)/6 with R_PP = (1/2) Tr(P Lambda(P)) the diagonal of
        the Pauli transfer matrix. (Check: depolarizing rho->(1-p)rho+p I/2 gives p/2.)
        """
        if self.n != 1:
            raise ValueError("avg_gate_infidelity implemented for single-qubit channels")
        r_diag = 0.0
        for P in (X, Y, Z):
            out = self.apply_channel(P, chan)
            r_diag += 0.5 * np.real(np.trace(P @ out))
        f_avg = (3.0 + r_diag) / 6.0
        return 1.0 - f_avg
