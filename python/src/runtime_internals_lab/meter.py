"""Counts CPython cycle-collector runs and their duration with `gc.callbacks`."""

from __future__ import annotations

import gc
import platform
import sys
import time
from types import TracebackType
from typing import Any


class GcMeter:
    """Context manager that records every collection while it is active."""

    def __init__(self) -> None:
        """Start with empty counters."""
        self.count = 0
        self.total_ns = 0
        self.max_ns = 0
        self.per_generation: dict[str, list[int]] = {}
        self._started = 0

    def _callback(self, phase: str, info: dict[str, Any]) -> None:
        """Time one collection from its start to its stop callback."""
        if phase == "start":
            self._started = time.perf_counter_ns()
            return
        took = time.perf_counter_ns() - self._started
        self.count += 1
        self.total_ns += took
        self.max_ns = max(self.max_ns, took)
        gen = self.per_generation.setdefault(f"generation {info.get('generation', '?')}", [0, 0])
        gen[0] += 1
        gen[1] += took

    def __enter__(self) -> GcMeter:
        """Install the callback."""
        gc.callbacks.append(self._callback)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Remove the callback."""
        gc.callbacks.remove(self._callback)

    def collectors(self) -> dict[str, dict[str, float]]:
        """Per-generation count and time in milliseconds."""
        return {k: {"count": v[0], "time_ms": v[1] / 1e6} for k, v in self.per_generation.items()}


def runtime_info() -> dict[str, Any]:
    """Interpreter facts recorded with every result: version, build and GC settings."""
    jit = getattr(sys, "_jit", None)
    gil = getattr(sys, "_is_gil_enabled", None)
    flags = [
        f"gc.threshold={','.join(str(t) for t in gc.get_threshold())}",
        f"gil={'off' if gil is not None and not gil() else 'on'}",
        f"jit={'on' if jit is not None and jit.is_enabled() else 'off'}",
    ]
    return {
        "runtime": "python",
        "version": platform.python_version(),
        "vm": f"{platform.python_implementation()} {platform.python_compiler()}",
        "flags": flags,
        "max_heap_bytes": None,
    }
