"""Loads and validates spec/workload.json, the reference values shared by all three runtimes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_SPEC_BYTES = 1 << 20


@dataclass(frozen=True)
class Check:
    """One reference checksum: running `ops` operations with `window` and `seed` gives `checksum`."""

    ops: int
    window: int
    seed: int
    checksum: int


@dataclass(frozen=True)
class Rounds:
    """Warm-up and measured rounds per process for one runtime."""

    warmup: int
    rounds: int


@dataclass(frozen=True)
class Bench:
    """Parameters of the cross-runtime comparison."""

    ops: int
    seed: int
    windows: tuple[int, ...]
    repeats: int
    rounds: dict[str, Rounds]


@dataclass(frozen=True)
class Spec:
    """The whole spec file."""

    xorshift32: tuple[tuple[int, tuple[int, ...]], ...]
    checks: tuple[Check, ...]
    bench: Bench

    def expected_checksum(self, ops: int, window: int, seed: int) -> int | None:
        """The reference checksum for these parameters, if the spec has one."""
        for c in self.checks:
            if (c.ops, c.window, c.seed) == (ops, window, seed):
                return c.checksum
        return None


def _int(obj: dict[str, Any], key: str, lo: int, hi: int) -> int:
    """Read an integer field and check its range (bool is not an int here)."""
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        raise ValueError(f"spec field {key!r} must be an integer in [{lo}, {hi}], got {value!r}")
    return value


def parse_spec(data: Any) -> Spec:
    """Validate the decoded JSON and build a `Spec`; raise ValueError on any mismatch."""
    if not isinstance(data, dict) or data.get("name") != "vector-churn" or data.get("version") != 1:
        raise ValueError("not a vector-churn version 1 spec")
    u32 = 0xFFFF_FFFF
    vectors = []
    for v in data.get("xorshift32", []):
        first = v.get("first")
        if not isinstance(first, list) or not first:
            raise ValueError("xorshift32 vectors need a non-empty 'first' list")
        values = tuple(_int({"x": x}, "x", 1, u32) for x in first)
        vectors.append((_int(v, "seed", 1, u32), values))
    checks = tuple(
        Check(
            ops=_int(c, "ops", 1, 100_000_000),
            window=_int(c, "window", 0, 1_000_000),
            seed=_int(c, "seed", 1, u32),
            checksum=_int(c, "checksum", 0, u32),
        )
        for c in data.get("checksums", [])
    )
    b = data.get("bench")
    if not isinstance(b, dict) or not vectors or not checks:
        raise ValueError("spec needs xorshift32 vectors, checksums and a bench section")
    windows = b.get("windows")
    if not isinstance(windows, list) or not windows:
        raise ValueError("bench.windows must be a non-empty list")
    rounds = {
        name: Rounds(_int(r, "warmup", 0, 1_000), _int(r, "rounds", 1, 1_000))
        for name, r in (b.get("rounds") or {}).items()
    }
    if set(rounds) != {"java", "node", "python"}:
        raise ValueError("bench.rounds must cover java, node and python")
    bench = Bench(
        ops=_int(b, "ops", 1, 100_000_000),
        seed=_int(b, "seed", 1, u32),
        windows=tuple(_int({"w": w}, "w", 0, 1_000_000) for w in windows),
        repeats=_int(b, "repeats", 1, 50),
        rounds=rounds,
    )
    return Spec(xorshift32=tuple(vectors), checks=checks, bench=bench)


def load_spec(path: Path) -> Spec:
    """Read and validate a spec file of bounded size."""
    if path.stat().st_size > MAX_SPEC_BYTES:
        raise ValueError(f"{path} is larger than {MAX_SPEC_BYTES} bytes")
    return parse_spec(json.loads(path.read_text(encoding="utf-8")))
