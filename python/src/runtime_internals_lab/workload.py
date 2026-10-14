"""The shared allocation-heavy workload ("vector-churn", spec/workload.md), CPython version."""

from __future__ import annotations

from runtime_internals_lab.xorshift import MASK32, XorShift32

MAX_OPS = 100_000_000
MAX_WINDOW = 1_000_000


class Vec:
    """Immutable-by-convention 2D integer vector; `__slots__` keeps it to two fields."""

    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        """Store the two components."""
        self.x = x
        self.y = y

    def add(self, o: Vec) -> Vec:
        """Component-wise sum, as a new object."""
        return Vec(self.x + o.x, self.y + o.y)

    def scale(self, k: int) -> Vec:
        """Both components times k, as a new object."""
        return Vec(self.x * k, self.y * k)


class VectorChurn:
    """Four `Vec` allocations per operation; with a window, the last one lives in a ring."""

    __slots__ = ("_ring", "window")

    def __init__(self, window: int) -> None:
        """Create the workload with a ring of `window` slots (0 = nothing retained)."""
        if not 0 <= window <= MAX_WINDOW:
            raise ValueError(f"window must be in [0, {MAX_WINDOW}]")
        self.window = window
        self._ring: list[Vec | None] = [None] * window

    def run(self, ops: int, seed: int) -> int:
        """Run one round of `ops` operations from `seed`; return the 32-bit checksum."""
        if not 1 <= ops <= MAX_OPS:
            raise ValueError(f"ops must be in [1, {MAX_OPS}]")
        window = self.window
        ring = self._ring
        for i in range(window):
            ring[i] = None
        rng = XorShift32(seed)
        checksum = 0
        slot = 0
        for _ in range(ops):
            r = rng.next()
            a = Vec(r & 0xFFFF, r >> 16)
            b = Vec(r >> 16, r & 0xFFFF)
            c = a.add(b).scale(3)
            if window:
                old = ring[slot]
                if old is not None:
                    checksum = (checksum + old.x) & MASK32
                ring[slot] = c
                slot = 0 if slot + 1 == window else slot + 1
            checksum = (checksum * 31 + c.x + c.y) & MASK32
        return checksum
