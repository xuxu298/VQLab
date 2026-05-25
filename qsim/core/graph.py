"""DeviceGraph — blocks + typed connections, with build-time type checking (spec §1-2)."""
from __future__ import annotations

from .block import Block
from .signals import SignalType


class DeviceGraph:
    """A directed graph of Blocks connected by typed ports.

    M0 only needs linear chains, but we implement a real topological sort and a
    port-type check so the abstraction is honest and extends to branched devices.
    """

    def __init__(self) -> None:
        self._blocks: dict[str, Block] = {}
        # edges: (src_block, src_port) -> (dst_block, dst_port)
        self._edges: list[tuple[str, str, str, str]] = []

    def add(self, block: Block) -> Block:
        if block.name in self._blocks:
            raise ValueError(f"duplicate block name: {block.name!r}")
        self._blocks[block.name] = block
        return block

    def connect(self, src: str, src_port: str, dst: str, dst_port: str) -> None:
        sb, db = self._blocks[src], self._blocks[dst]
        st: SignalType = sb.ports_out[src_port]
        dt: SignalType = db.ports_in[dst_port]
        if st != dt:
            raise TypeError(
                f"port type mismatch {src}.{src_port} ({st}) -> {dst}.{dst_port} ({dt})"
            )
        self._edges.append((src, src_port, dst, dst_port))

    def topo_order(self) -> list[Block]:
        """Kahn topological sort over block-level dependencies."""
        deps: dict[str, set[str]] = {name: set() for name in self._blocks}
        for src, _sp, dst, _dp in self._edges:
            deps[dst].add(src)
        order: list[str] = []
        ready = [n for n, d in deps.items() if not d]
        while ready:
            n = ready.pop(0)
            order.append(n)
            for m, d in deps.items():
                if n in d:
                    d.discard(n)
                    if not d and m not in order and m not in ready:
                        ready.append(m)
        if len(order) != len(self._blocks):
            raise ValueError("graph has a cycle")
        return [self._blocks[n] for n in order]

    def get(self, name: str) -> Block:
        return self._blocks[name]
