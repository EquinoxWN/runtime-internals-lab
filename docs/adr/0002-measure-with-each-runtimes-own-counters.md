# ADR 0002: Measure with each runtime's own counters, one fresh process per configuration

- **Status:** Accepted

## Context

The project compares how three runtimes treat the same allocation-heavy loop. The numbers that
matter are bytes allocated per operation, how often the collector runs and how long it takes, and
time per operation. Each ecosystem has its own benchmark framework (JMH, pyperf, mitata) and its
own profilers, and they report different statistics in different formats. JIT state also
accumulates: a JVM that has already compiled one configuration's loop, or grown its young
generation for it, measures the next configuration differently.

## Decision

- Each runtime gets a small harness that reads its own built-in counters around the measured
  rounds and prints one JSON line in a shared format:
  - **Java:** `com.sun.management.ThreadMXBean.getCurrentThreadAllocatedBytes()` (exact bytes
    allocated by the measuring thread, from TLAB accounting) and the `GarbageCollectorMXBean`s.
  - **Node.js:** `v8.GCProfiler`, which reports every GC with its type, cost and the heap statistics
    before and after; allocated bytes are the growth of the used heap between collections.
  - **CPython:** `gc.callbacks`, timing every cycle-collector run from its start to its stop.
- Every configuration runs in a fresh process, 5 times, interleaved with the other configurations.
- A Python runner validates each line (exact field set and types), checks the checksum against the
  spec, and reports medians with min-max ranges.

## Consequences

- One contract covers three runtimes; adding a runtime means writing one harness, and the runner,
  validation and tables stay the same.
- Java bytes per operation are exact, so "the fixed variant allocates 0 B/op" is a hard check
  (CI gate and unit test), independent of machine load.
- Wall-clock numbers are less precise than JMH's (no forking strategy, no blackhole, no
  statistical warm-up detection). The effects M1 reports are about 1.4x to 4.4x in time and 24 to 96
  B/op in allocation, far above that loss; sub-nanosecond claims would need JMH (M3).
- Resolution differs: HotSpot's GC time is in milliseconds, V8's in microseconds, CPython's in
  nanoseconds. Per-pause JVM analysis is left to Java Flight Recorder in M2.
- CPython allocated bytes are not measured in M1 (no cheap total-allocation counter exists); the
  table says "not measured" rather than estimating.
- A full `make bench` costs about 2 minutes (50 processes), mostly CPython.
