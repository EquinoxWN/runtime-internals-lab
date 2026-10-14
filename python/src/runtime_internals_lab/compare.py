"""Runs the experiments in every runtime, checks the results and writes Markdown tables.

usage: python -m runtime_internals_lab.compare churn  [--repeats N] [--repo DIR]
       python -m runtime_internals_lab.compare escape [--repeats N] [--repo DIR]

`churn` runs the shared vector-churn workload in Java, Node.js and CPython (each configuration in a
fresh process, `--repeats` times, interleaved) and fails with exit code 3 if any checksum differs
from spec/workload.json. `escape` runs the Java escape-analysis cases with escape analysis on and
off, plus one run with -XX:+LogCompilation, and fails with exit code 3 if a fixed variant still
allocates, an escaping one stops allocating, or the log shows no eliminated allocation for a fixed
variant. Every JVM writes crash files, heap dumps and logs only under the repo's .tmp/ folder.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from runtime_internals_lab import jitlog
from runtime_internals_lab.results import ChurnResult, EscapeResult, ProbeResult, Summary, summarize
from runtime_internals_lab.spec import Spec, load_spec

PROCESS_TIMEOUT_S = 600
ESCAPE_MAIN = "portfolio.runtimeinternalslab.cli.EscapeMain"
CHURN_MAIN = "portfolio.runtimeinternalslab.cli.ChurnMain"
ESCAPE_CLASSES = ("portfolio.runtimeinternalslab.escape.EscapeCases", "portfolio.runtimeinternalslab.workload.Vec")
VEC = "portfolio.runtimeinternalslab.workload.Vec"
KERNELS = {
    ("temporaries", "control"): "temporaries",
    ("branch-merge", "escapes"): "branchMergeEscapes",
    ("branch-merge", "fixed"): "branchMergeFixed",
    ("loop-accumulator", "escapes"): "loopAccumulatorEscapes",
    ("loop-accumulator", "fixed"): "loopAccumulatorFixed",
    ("static-store", "escapes"): "staticStoreEscapes",
    ("static-store", "fixed"): "staticStoreFixed",
}
ZERO_ALLOC = 0.5
ONE_VEC = 23.9


@dataclass(frozen=True)
class Config:
    """One runtime configuration of the churn comparison."""

    label: str
    runtime: str
    extra_flags: tuple[str, ...]


CONFIGS = (
    Config("Java (C2, escape analysis on)", "java", ()),
    Config("Java (-XX:-DoEscapeAnalysis)", "java", ("-XX:-DoEscapeAnalysis",)),
    Config("Node.js (TurboFan, escape analysis on)", "node", ()),
    Config("Node.js (--no-turbo-escape)", "node", ("--no-turbo-escape",)),
    Config("CPython", "python", ()),
)


class Lab:
    """Paths and commands for one repository checkout."""

    def __init__(self, repo: Path) -> None:
        """Locate the spec, the compiled Java classes and the scratch folder."""
        self.repo = repo.resolve()
        self.spec_path = self.repo / "spec" / "workload.json"
        if not self.spec_path.is_file():
            raise SystemExit(f"error: {self.spec_path} not found; run from the repository root or pass --repo")
        self.classes = self.repo / "java" / "target" / "classes"
        self.tmp = self.repo / ".tmp"
        self.out = self.tmp / "results"
        self.out.mkdir(parents=True, exist_ok=True)
        self.java = _tool("java")
        self.node = _tool("node")

    def jvm_flags(self) -> list[str]:
        """Heap cap and every file a JVM may write, inside .tmp/ (no hsperfdata at all)."""
        return [
            "-Xmx512m",
            "-XX:+UseG1GC",
            "-XX:-UsePerfData",
            f"-XX:ErrorFile={self.tmp / 'hs_err_pid%p.log'}",
            f"-XX:HeapDumpPath={self.tmp}",
            f"-Djava.io.tmpdir={self.tmp}",
        ]

    def command(self, config: Config, window: int, spec: Spec) -> list[str]:
        """Command line for one churn process."""
        b = spec.bench
        r = b.rounds[config.runtime]
        args = ["--ops", str(b.ops), "--window", str(window), "--seed", str(b.seed)]
        args += ["--warmup", str(r.warmup), "--rounds", str(r.rounds)]
        if config.runtime == "java":
            return [self.java, *self.jvm_flags(), *config.extra_flags, "-cp", str(self.classes), CHURN_MAIN, *args]
        if config.runtime == "node":
            script = self.repo / "js" / "src" / "churn.js"
            return [self.node, "--max-old-space-size=512", *config.extra_flags, str(script), *args]
        return [sys.executable, "-m", "runtime_internals_lab.churn", *args]

    def sanitize(self, text: str) -> str:
        """Replace the absolute repository path, so recorded flags carry no local paths."""
        return text.replace(str(self.repo), "<repo>").replace(str(self.repo).replace("\\", "/"), "<repo>")


def _tool(name: str) -> str:
    """Absolute path of an executable on PATH."""
    found = shutil.which(name)
    if found is None:
        raise SystemExit(f"error: {name} not found on PATH")
    return found


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> list[str]:
    """Run a command (no shell) and return its non-empty stdout lines; fail loudly on errors."""
    proc = subprocess.run(  # noqa: S603
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=PROCESS_TIMEOUT_S, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{Path(cmd[0]).name} exited with {proc.returncode}: {proc.stderr.strip()[-2000:]}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def run_churn(lab: Lab, spec: Spec, repeats: int) -> int:
    """Cross-runtime comparison; returns the exit code."""
    results: dict[tuple[str, int], list[ChurnResult]] = {}
    raw: list[str] = []
    for rep in range(repeats):
        for config in CONFIGS:
            for window in spec.bench.windows:
                lines = _run(lab.command(config, window, spec), lab.repo)
                if len(lines) != 1:
                    raise RuntimeError(f"{config.label} printed {len(lines)} lines, expected one result")
                raw.append(lab.sanitize(lines[0]))
                results.setdefault((config.label, window), []).append(ChurnResult.parse(lines[0]))
                print(f"run {rep + 1}/{repeats}: {config.label}, window {window:,}", file=sys.stderr)
    (lab.out / "churn.jsonl").write_text("\n".join(raw) + "\n", encoding="utf-8")
    bad = [
        f"{label} window {w}: {r.checksum}"
        for (label, w), rs in results.items()
        for r in rs
        if r.checksum != spec.expected_checksum(r.ops, r.window, r.seed)
    ]
    table = churn_table(results)
    (lab.out / "churn.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    print()
    print(versions(results, lab))
    runs = sum(len(rs) for rs in results.values())
    status = "yes" if not bad else "no"
    print(f"RESULT checksums_match_spec={status} runs={runs} configs={len(results)} repeats={repeats}")
    for line in bad:
        print(f"checksum mismatch: {line}", file=sys.stderr)
    return 0 if not bad else 3


def churn_table(results: dict[tuple[str, int], list[ChurnResult]]) -> str:
    """Markdown table: one row per configuration and window, medians with min-max ranges."""
    rows = [
        "| Runtime | Window | ns/op, median [min-max] | Spread | Allocated B/op "
        "| GCs per 1M ops | GC ms per 1M ops | Checksum |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for (label, window), rs in results.items():
        ns = summarize([r.ns_per_op for r in rs])
        allocs = [r.alloc_bytes_per_op for r in rs if r.alloc_bytes_per_op is not None]
        alloc = summarize(allocs).fmt(1) if len(allocs) == len(rs) else "not measured"
        gcs = summarize([r.gc_count * 1e6 / r.measured_ops for r in rs])
        gcms = summarize([r.gc_time_ms * 1e6 / r.measured_ops for r in rs])
        checks = {r.checksum for r in rs}
        rows.append(
            f"| {label} | {window:,} | {ns.fmt(1)} | {ns.spread:.0%} | {alloc} | {gcs.fmt(1)} | {gcms.fmt(2)} | "
            f"{', '.join(str(c) for c in sorted(checks))} |"
        )
    return "\n".join(rows)


def versions(results: dict[tuple[str, int], list[ChurnResult]], lab: Lab) -> str:
    """One line per runtime with version, VM and flags of the first run."""
    seen: dict[str, str] = {}
    for (label, _), rs in results.items():
        r = rs[0]
        seen.setdefault(label, f"- {label}: {r.version}, {r.vm}; flags: {lab.sanitize(' '.join(r.flags)) or '(none)'}")
    return "\n".join(seen.values())


def run_escape(lab: Lab, repeats: int) -> int:
    """Escape-analysis experiment with measurements, log analysis and gates; returns the exit code."""
    base = [lab.java, *lab.jvm_flags(), "-cp", str(lab.classes), ESCAPE_MAIN]
    measured: dict[str, dict[tuple[str, str], list[EscapeResult]]] = {"on": {}, "off": {}}
    raw: list[str] = []
    for _ in range(repeats):
        for mode, extra in (("on", []), ("off", ["-XX:-DoEscapeAnalysis"])):
            cmd = [*base[:-1], *extra, base[-1], "--ops", "1000000", "--warmup", "30", "--rounds", "10"]
            for line in _run(cmd, lab.repo):
                raw.append(lab.sanitize(line))
                r = EscapeResult.parse(line)
                measured[mode].setdefault((r.case, r.variant), []).append(r)
    (lab.out / "escape.jsonl").write_text("\n".join(raw) + "\n", encoding="utf-8")

    jit_dir = lab.tmp / "jit"
    jit_dir.mkdir(parents=True, exist_ok=True)
    log = jit_dir / "escape-compilation.log"
    log.unlink(missing_ok=True)
    log_flags = ["-XX:+UnlockDiagnosticVMOptions", "-XX:+LogCompilation", f"-XX:LogFile={log}"]
    # HotSpot writes per-compiler-thread hs_c*.log files to the OS temp folder (TMP on Windows) and
    # merges them into the log at exit; point TMP and TEMP at .tmp/jit so they never land elsewhere.
    jit_env = {**os.environ, "TMP": str(jit_dir), "TEMP": str(jit_dir), "TMPDIR": str(jit_dir)}
    _run([*base[:-1], *log_flags, base[-1], "--ops", "1000000", "--warmup", "30", "--rounds", "1"], jit_dir, jit_env)
    javap = _run([_tool("javap"), "-l", "-p", "-cp", str(lab.classes), *ESCAPE_CLASSES], lab.repo)
    tables = jitlog.line_tables("\n".join(javap))
    tasks = jitlog.parse(log)
    sites = jitlog.summarize(tasks, "portfolio.runtimeinternalslab.escape.EscapeCases.", tables)

    report, failures = escape_report(measured, sites)
    report += "\n\n" + v8_probe(lab, repeats)
    (lab.out / "escape.md").write_text(report + "\n", encoding="utf-8")
    print(report)
    print()
    print(f"RESULT {' '.join(failures['summary'])}")
    for problem in failures["problems"]:
        print(f"gate failed: {problem}", file=sys.stderr)
    return 3 if failures["problems"] else 0


def v8_probe(lab: Lab, repeats: int) -> str:
    """The same temporaries in Node.js, with TurboFan's escape analysis on and off (reported, not gated)."""
    script = str(lab.repo / "js" / "src" / "escape-probe.js")
    probes: dict[str, dict[str, list[ProbeResult]]] = {"on": {}, "off": {}}
    for _ in range(repeats):
        for mode, extra in (("on", []), ("off", ["--no-turbo-escape"])):
            for line in _run([lab.node, "--max-old-space-size=512", *extra, script], lab.repo):
                r = ProbeResult.parse(line)
                if not r.agrees:
                    raise RuntimeError(f"V8 probe kernel {r.kernel} disagreed")
                probes[mode].setdefault(r.kernel, []).append(r)
    rows = [
        "V8 for comparison (`js/src/escape-probe.js`, the same arithmetic as `temporaries`):",
        "",
        "| Kernel | B/op, escape analysis on | B/op, --no-turbo-escape | ns/op on | ns/op off |",
        "|---|---|---|---|---|",
    ]
    for kernel, on in probes["on"].items():
        off = probes["off"][kernel]
        b_on = summarize([r.alloc_bytes_per_op for r in on])
        b_off = summarize([r.alloc_bytes_per_op for r in off])
        t_on = summarize([r.ns_per_op for r in on])
        t_off = summarize([r.ns_per_op for r in off])
        rows.append(f"| {kernel} | {b_on.fmt(1)} | {b_off.fmt(1)} | {t_on.fmt(2)} | {t_off.fmt(2)} |")
    return "\n".join(rows)


def escape_report(
    measured: dict[str, dict[tuple[str, str], list[EscapeResult]]], sites: list[jitlog.SiteReport]
) -> tuple[str, dict[str, list[str]]]:
    """Markdown tables for the escape experiment plus the gate verdicts."""
    eliminated: dict[str, int] = {}
    for s in sites:
        if s.type_name == VEC:
            name = s.root.rsplit(".", 1)[-1]
            eliminated[name] = eliminated.get(name, 0) + 1
    rows = [
        "| Case | Variant | B/op, EA on | B/op, EA off | ns/op EA on, median [min-max] "
        "| ns/op EA off, median [min-max] | Vec sites removed in the log |",
        "|---|---|---|---|---|---|---|",
    ]
    problems: list[str] = []
    agree = True
    fixed_ok = fixed_total = esc_ok = esc_total = logged_ok = 0
    for key, kernel in KERNELS.items():
        on = measured["on"].get(key, [])
        off = measured["off"].get(key, [])
        if not on or not off:
            problems.append(f"{key} was not measured")
            continue
        agree = agree and all(r.agrees for r in on + off) and len({r.result for r in on + off}) == 1
        b_on: Summary = summarize([r.alloc_bytes_per_op for r in on])
        b_off: Summary = summarize([r.alloc_bytes_per_op for r in off])
        t_on = summarize([r.ns_per_op for r in on])
        t_off = summarize([r.ns_per_op for r in off])
        removed = eliminated.get(kernel, 0)
        if key[1] == "escapes":
            esc_total += 1
            if b_on.low >= ONE_VEC:
                esc_ok += 1
            else:
                problems.append(f"{key[0]} escapes allocated only {b_on.low:.2f} B/op")
        else:
            fixed_total += 1
            if b_on.high < ZERO_ALLOC:
                fixed_ok += 1
            else:
                problems.append(f"{key[0]} {key[1]} still allocates {b_on.high:.2f} B/op")
            if removed > 0:
                logged_ok += 1
            else:
                problems.append(f"no eliminated Vec allocation logged for {kernel}")
        rows.append(
            f"| {key[0]} | {key[1]} | {b_on.fmt(1)} | {b_off.fmt(1)} | {t_on.fmt(2)} | {t_off.fmt(2)} | {removed} |"
        )
    if not agree:
        problems.append("escapes and fixed variants returned different results")
    summary = [
        f"pairs_agree={'yes' if agree else 'no'}",
        f"fixed_zero_alloc={fixed_ok}/{fixed_total}",
        f"escaping_still_allocate={esc_ok}/{esc_total}",
        f"log_eliminations_in_fixed={logged_ok}/{fixed_total}",
    ]
    report = "\n".join(rows) + "\n\nEliminated allocations in the -XX:+LogCompilation log:\n\n" + jitlog.render(sites)
    return report, {"summary": summary, "problems": problems}


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point."""
    p = argparse.ArgumentParser(prog="compare", allow_abbrev=False)
    p.add_argument("experiment", choices=("churn", "escape"))
    p.add_argument("--repeats", type=int, default=0, help="process launches per configuration (default: spec)")
    p.add_argument("--repo", type=Path, default=Path.cwd())
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    lab = Lab(args.repo)
    spec = load_spec(lab.spec_path)
    repeats = args.repeats or spec.bench.repeats
    if not 1 <= repeats <= 50:
        raise SystemExit("error: --repeats must be in [1, 50]")
    if not (lab.classes / "portfolio").is_dir():
        raise SystemExit("error: java/target/classes is missing; run `mvn -DskipTests compile` in java/ first")
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if args.experiment == "churn":
        return run_churn(lab, spec, repeats)
    return run_escape(lab, repeats)


if __name__ == "__main__":
    raise SystemExit(main())
