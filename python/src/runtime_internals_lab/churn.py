"""Run the vector-churn workload in CPython and print one JSON result line.

usage: python -m runtime_internals_lab.churn --ops N --window W --seed S --warmup K --rounds R
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from typing import Any

from runtime_internals_lab.meter import GcMeter, runtime_info
from runtime_internals_lab.workload import MAX_OPS, MAX_WINDOW, VectorChurn


def bounded(lo: int, hi: int) -> Any:
    """argparse type: an integer in [lo, hi]."""

    def parse(raw: str) -> int:
        """Parse and range-check one value."""
        value = int(raw)
        if not lo <= value <= hi:
            raise argparse.ArgumentTypeError(f"must be in [{lo}, {hi}]")
        return value

    return parse


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse the same options the Java and JavaScript harnesses take."""
    p = argparse.ArgumentParser(prog="churn", allow_abbrev=False)
    p.add_argument("--ops", type=bounded(1, MAX_OPS), default=1_000_000)
    p.add_argument("--window", type=bounded(0, MAX_WINDOW), default=0)
    p.add_argument("--seed", type=bounded(1, 0xFFFF_FFFF), default=42)
    p.add_argument("--warmup", type=bounded(0, 1_000), default=1)
    p.add_argument("--rounds", type=bounded(1, 1_000), default=3)
    return p.parse_args(argv)


def measure(ops: int, window: int, seed: int, warmup: int, rounds: int) -> dict[str, Any]:
    """Run warm-up rounds, then measure `rounds` rounds; every round must agree."""
    churn = VectorChurn(window)
    checksum = -1
    for _ in range(warmup):
        checksum = same(checksum, churn.run(ops, seed))
    with GcMeter() as gcm:
        start = time.perf_counter_ns()
        for _ in range(rounds):
            checksum = same(checksum, churn.run(ops, seed))
        wall = time.perf_counter_ns() - start
    total = ops * rounds
    return {
        **runtime_info(),
        "workload": "vector-churn",
        "ops": ops,
        "window": window,
        "seed": seed,
        "warmup": warmup,
        "rounds": rounds,
        "checksum": checksum,
        "wall_ns": wall,
        "ns_per_op": wall / total,
        "alloc_bytes": None,
        "alloc_bytes_per_op": None,
        "gc_count": gcm.count,
        "gc_time_ms": gcm.total_ns / 1e6,
        "collectors": gcm.collectors(),
    }


def same(previous: int, actual: int) -> int:
    """Every round from the same seed must give the same checksum (-1 = none yet)."""
    if previous not in (-1, actual):
        raise RuntimeError(f"checksum changed between rounds: {previous} vs {actual}")
    return actual


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    line = measure(args.ops, args.window, args.seed, args.warmup, args.rounds)
    print(json.dumps(line, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
