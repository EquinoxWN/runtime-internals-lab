# ADR 0003: Prove scalar replacement from C2's LogCompilation output, not debug-build flags

- **Status:** Accepted

## Context

M1 must show which objects escape analysis keeps off the heap, not only that allocation went
down. HotSpot has flags that print escape-analysis decisions directly
(`-XX:+PrintEscapeAnalysis`, `-XX:+PrintEliminateAllocations`), but they are compiled only into
debug builds of the JVM. Readers and CI use release JDKs (Temurin 21). The alternatives on a
release JDK are the allocation counters alone (which show the effect but not the cause), or
`-XX:+UnlockDiagnosticVMOptions -XX:+LogCompilation`, an XML log of every compilation that, in
C2, contains one `<eliminate_allocation type=... >` element per removed allocation, with the
inlining stack of the `new` bytecode as `<jvms bci=... method=...>` children.

## Decision

- Run the escape-analysis cases once with `-XX:+LogCompilation -XX:LogFile=.tmp/jit/...` and read
  the log with a streaming parser (`runtime_internals_lab.jitlog`): it scopes `klass` and `method`
  ids to the `<task>` that declares them (ids are reused across tasks), keeps only successful C2
  tasks, and reports each eliminated site once per compiled method with the number of C2 tasks
  that removed it.
- Map bytecode indexes to source lines with `javap -l -p` output, so the report says
  "`EscapeCases.branchMergeFixed@64 (line 94)`" instead of a bare bci.
- Treat the log as untrusted input: a size limit, and any `DOCTYPE` or `ENTITY` declaration is
  refused before it reaches the XML parser, so entity expansion cannot happen.
- Gate on both views: a fixed variant must measure below 0.5 B/op and have at least one logged
  `Vec` elimination; an escaping variant must still allocate 24 B/op.

## Consequences

- Works on any release JDK 21, locally and in CI, with no custom JVM build.
- The log shows partial cases precisely: in `loop-accumulator` (escaping) the per-step `Vec` is
  eliminated while the accumulator carried around the loop is not, which matches the measured
  24 B/op (one object) instead of 48 B/op (two, with escape analysis off).
- The log names what was removed, not why something was kept: there is no
  "not scalar replaceable: merged" message in release builds. The reason for each kept allocation
  comes from the escape-analysis rules (merge at a control-flow join, loop-carried value, store to
  a static field) and is confirmed by the fixed variant, which differs only in that one respect.
- The element names are a HotSpot implementation detail; a JDK that renames them would make the
  log gate fail in CI, which is the intended signal. The parser is tested against a trimmed real
  JDK 21 log kept in `python/tests/fixtures/`.
- While it runs, LogCompilation writes one `hs_c<thread>_pid<pid>.log` file per compiler thread
  to the operating system's temp folder (seen on this machine in the folder `TMP` points to) and
  merges them into the log at exit. The runner starts that JVM with `TMP`, `TEMP` and `TMPDIR` set
  to `.tmp/jit/`, so the files stay inside the repository.
