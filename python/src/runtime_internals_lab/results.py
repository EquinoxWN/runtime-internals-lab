"""Strict parsing of the JSON result lines every harness prints, and summary statistics."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from typing import Any

MAX_LINE_BYTES = 64 * 1024

_COMMON = {
    "runtime": str,
    "version": str,
    "vm": str,
    "flags": list,
    "max_heap_bytes": (int, type(None)),
    "ops": int,
    "seed": int,
    "warmup": int,
    "rounds": int,
    "wall_ns": int,
    "ns_per_op": (int, float),
    "alloc_bytes": (int, type(None)),
    "alloc_bytes_per_op": (int, float, type(None)),
    "gc_count": int,
    "gc_time_ms": (int, float),
}
CHURN_FIELDS = {**_COMMON, "workload": str, "window": int, "checksum": int, "collectors": dict}
ESCAPE_FIELDS = {
    **_COMMON,
    "experiment": str,
    "case": str,
    "variant": str,
    "result": int,
    "agrees": bool,
}

PROBE_FIELDS = {
    "runtime": str,
    "version": str,
    "vm": str,
    "flags": list,
    "max_heap_bytes": (int, type(None)),
    "experiment": str,
    "kernel": str,
    "ops": int,
    "rounds": int,
    "result": (int, float),
    "agrees": bool,
    "ns_per_op": (int, float),
    "alloc_bytes_per_op": (int, float),
    "gc_count": int,
}


def _check(line: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Decode one line and require exactly the expected fields with the expected types."""
    if len(line.encode("utf-8")) > MAX_LINE_BYTES:
        raise ValueError("result line is too long")
    data = json.loads(line)
    if not isinstance(data, dict):
        raise ValueError("result line is not a JSON object")
    missing = fields.keys() - data.keys()
    extra = data.keys() - fields.keys()
    if missing or extra:
        raise ValueError(f"result fields differ: missing {sorted(missing)}, unexpected {sorted(extra)}")
    for key, kind in fields.items():
        value = data[key]
        if isinstance(value, bool) and kind is not bool:
            raise ValueError(f"{key} must not be a boolean")
        if not isinstance(value, kind):
            raise ValueError(f"{key} has the wrong type: {type(value).__name__}")
    if not all(isinstance(f, str) for f in data["flags"]):
        raise ValueError("flags must be strings")
    if data["ops"] < 1 or data["rounds"] < 1 or data.get("wall_ns", 1) <= 0 or data["gc_count"] < 0:
        raise ValueError("ops, rounds, wall_ns and gc_count must be positive")
    return data


@dataclass(frozen=True)
class ChurnResult:
    """One process run of the vector-churn workload."""

    runtime: str
    version: str
    vm: str
    flags: tuple[str, ...]
    window: int
    ops: int
    seed: int
    rounds: int
    checksum: int
    ns_per_op: float
    alloc_bytes_per_op: float | None
    gc_count: int
    gc_time_ms: float

    @classmethod
    def parse(cls, line: str) -> ChurnResult:
        """Validate and convert one result line."""
        d = _check(line, CHURN_FIELDS)
        if d["workload"] != "vector-churn" or not 0 <= d["checksum"] <= 0xFFFF_FFFF:
            raise ValueError("not a vector-churn result with a 32-bit checksum")
        return cls(
            runtime=d["runtime"],
            version=d["version"],
            vm=d["vm"],
            flags=tuple(d["flags"]),
            window=d["window"],
            ops=d["ops"],
            seed=d["seed"],
            rounds=d["rounds"],
            checksum=d["checksum"],
            ns_per_op=float(d["ns_per_op"]),
            alloc_bytes_per_op=None if d["alloc_bytes_per_op"] is None else float(d["alloc_bytes_per_op"]),
            gc_count=d["gc_count"],
            gc_time_ms=float(d["gc_time_ms"]),
        )

    @property
    def measured_ops(self) -> int:
        """Operations in the measured window."""
        return self.ops * self.rounds


@dataclass(frozen=True)
class EscapeResult:
    """One escape-analysis variant measured in one JVM."""

    case: str
    variant: str
    flags: tuple[str, ...]
    result: int
    agrees: bool
    ns_per_op: float
    alloc_bytes_per_op: float

    @classmethod
    def parse(cls, line: str) -> EscapeResult:
        """Validate and convert one result line."""
        d = _check(line, ESCAPE_FIELDS)
        if d["experiment"] != "escape" or d["variant"] not in ("control", "escapes", "fixed"):
            raise ValueError("not an escape-analysis result")
        if d["alloc_bytes_per_op"] is None:
            raise ValueError("escape results must report allocated bytes")
        return cls(
            case=d["case"],
            variant=d["variant"],
            flags=tuple(d["flags"]),
            result=d["result"],
            agrees=d["agrees"],
            ns_per_op=float(d["ns_per_op"]),
            alloc_bytes_per_op=float(d["alloc_bytes_per_op"]),
        )


@dataclass(frozen=True)
class ProbeResult:
    """One V8 escape-probe kernel measured in one Node.js process."""

    kernel: str
    flags: tuple[str, ...]
    result: float
    agrees: bool
    ns_per_op: float
    alloc_bytes_per_op: float

    @classmethod
    def parse(cls, line: str) -> ProbeResult:
        """Validate and convert one result line."""
        d = _check(line, PROBE_FIELDS)
        if d["experiment"] != "v8-escape" or d["kernel"] not in ("methods", "inline", "none"):
            raise ValueError("not a V8 escape-probe result")
        return cls(
            kernel=d["kernel"],
            flags=tuple(d["flags"]),
            result=float(d["result"]),
            agrees=d["agrees"],
            ns_per_op=float(d["ns_per_op"]),
            alloc_bytes_per_op=float(d["alloc_bytes_per_op"]),
        )


@dataclass(frozen=True)
class Summary:
    """Median and range of repeated measurements."""

    median: float
    low: float
    high: float
    n: int

    @property
    def spread(self) -> float:
        """(max - min) / median; 0 when the median is 0."""
        return (self.high - self.low) / self.median if self.median else 0.0

    def fmt(self, digits: int = 1) -> str:
        """`median [min-max]` with the given decimals."""
        return f"{self.median:,.{digits}f} [{self.low:,.{digits}f}-{self.high:,.{digits}f}]"


def summarize(values: list[float]) -> Summary:
    """Median, minimum and maximum of a non-empty list."""
    if not values:
        raise ValueError("nothing to summarize")
    return Summary(statistics.median(values), min(values), max(values), len(values))
