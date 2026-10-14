# The shared workload: vector-churn

One allocation-heavy loop, written three times (Java, Python, JavaScript) so the runtimes can be
compared on exactly the same work. Every implementation must produce the checksums in
[`workload.json`](workload.json); the test suites and the experiment runner check this.

## Inputs

| Input | Range | Meaning |
|---|---|---|
| `ops` | 1 to 100,000,000 | operations per round |
| `window` | 0 to 1,000,000 | ring size: how many recent results stay reachable (0 = none) |
| `seed` | 1 to 2^32 - 1 | xorshift32 seed (zero is a fixed point and is rejected) |

## Random source

Marsaglia's xorshift32 on an unsigned 32-bit state `x`:
`x ^= x << 13; x ^= x >> 17; x ^= x << 5` (all modulo 2^32), and `x` is the output.
Seed 1 gives 270369, 67634689, 2647435461 (the first values in `workload.json`).

## One round

```
rng      = xorshift32(seed)
ring     = window empty slots (cleared at the start of every round)
checksum = 0
for i in 0 .. ops-1:
    r = rng.next()
    a = Vec(r & 0xFFFF, r >> 16)          # allocation 1
    b = Vec(r >> 16, r & 0xFFFF)          # allocation 2
    c = a.add(b).scale(3)                 # allocations 3 and 4 (each returns a new Vec)
    if window > 0:
        old = ring[i mod window]
        if old is not empty: checksum = (checksum + old.x) mod 2^32
        ring[i mod window] = c            # c stays reachable for `window` operations
    checksum = (checksum * 31 + c.x + c.y) mod 2^32
return checksum
```

`Vec` is an immutable pair of integers; `add` and `scale` return new objects. With `window = 0`
all four objects are garbage at the end of the operation, which is the case escape analysis can
remove entirely. With `window > 0` the last object escapes into the ring and lives for `window`
operations: a "middle-aged" object that survives at least one young collection.

All intermediate values stay below 2^53, so JavaScript numbers are exact.

## Harness contract

Each runtime has a command that runs `warmup` unmeasured rounds and then `rounds` measured rounds,
checks that every round returned the same checksum, and prints one JSON line:

| Field | Java | Node.js | CPython |
|---|---|---|---|
| `ns_per_op` | `System.nanoTime` | `process.hrtime.bigint` | `time.perf_counter_ns` |
| `alloc_bytes` | per-thread allocation counter (`ThreadMXBean`) | used heap before/after every GC (`v8.GCProfiler`) | not measured (null) |
| `gc_count`, `gc_time_ms` | `GarbageCollectorMXBean` (millisecond resolution) | `v8.GCProfiler` cost per GC (microseconds) | `gc.callbacks` start/stop (nanoseconds) |
| `flags`, `version`, `vm` | JVM input arguments, `java.vm.version` | `process.execArgv`, Node and V8 versions | GC thresholds, GIL and JIT state |

The Python runner (`runtime_internals_lab.results`) rejects any line with a missing, extra or
mistyped field.
