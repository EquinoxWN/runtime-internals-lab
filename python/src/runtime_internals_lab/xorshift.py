"""Marsaglia's xorshift32 generator (shifts 13, 17, 5), shared bit-for-bit with Java and JS."""

from __future__ import annotations

MASK32 = 0xFFFF_FFFF


class XorShift32:
    """32-bit xorshift generator; outputs are unsigned ints below 2**32."""

    __slots__ = ("_state",)

    def __init__(self, seed: int) -> None:
        """Start from a non-zero 32-bit seed (zero is a fixed point)."""
        if not 0 < seed <= MASK32:
            raise ValueError("xorshift32 seed must be in [1, 2**32 - 1]")
        self._state = seed

    def next(self) -> int:
        """Next 32 random bits."""
        x = self._state
        x ^= (x << 13) & MASK32
        x ^= x >> 17
        x ^= (x << 5) & MASK32
        self._state = x
        return x
