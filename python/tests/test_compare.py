"""The experiment runner keeps every JVM file inside .tmp/ and its gates catch regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime_internals_lab import compare
from runtime_internals_lab.jitlog import SiteReport
from runtime_internals_lab.results import ChurnResult, EscapeResult
from runtime_internals_lab.spec import Spec


@pytest.fixture
def lab(repo: Path) -> compare.Lab:
    """A lab rooted at this checkout."""
    return compare.Lab(repo)


def test_every_jvm_launch_caps_the_heap_and_writes_only_inside_tmp(lab: compare.Lab, spec: Spec) -> None:
    for config in compare.CONFIGS:
        cmd = lab.command(config, 0, spec)
        if config.runtime != "java":
            continue
        assert "-Xmx512m" in cmd
        assert "-XX:-UsePerfData" in cmd
        for prefix in ("-XX:ErrorFile=", "-XX:HeapDumpPath=", "-Djava.io.tmpdir="):
            value = next(a for a in cmd if a.startswith(prefix))[len(prefix) :]
            assert Path(value.replace("%p", "0")).resolve().is_relative_to(lab.tmp)


def test_node_and_python_commands_use_the_spec_rounds(lab: compare.Lab, spec: Spec) -> None:
    node = lab.command(compare.CONFIGS[2], 100_000, spec)
    assert node[1] == "--max-old-space-size=512"
    assert node[node.index("--rounds") + 1] == str(spec.bench.rounds["node"].rounds)
    py = lab.command(compare.CONFIGS[4], 0, spec)
    assert py[1:3] == ["-m", "runtime_internals_lab.churn"]
    assert py[py.index("--warmup") + 1] == str(spec.bench.rounds["python"].warmup)


def test_recorded_flags_carry_no_local_paths(lab: compare.Lab) -> None:
    text = f"-XX:ErrorFile={lab.tmp / 'x.log'}"
    assert lab.sanitize(text) == f"-XX:ErrorFile={Path('<repo>') / '.tmp' / 'x.log'}"


def escape_result(case: str, variant: str, alloc: float, result: int = 7) -> EscapeResult:
    """A synthetic measurement."""
    return EscapeResult(case, variant, (), result, True, 3.0, alloc)


def healthy() -> dict[str, dict[tuple[str, str], list[EscapeResult]]]:
    """Measurements that pass every gate."""
    on = {key: [escape_result(*key, 24.0 if key[1] == "escapes" else 0.0)] for key in compare.KERNELS}
    off = {key: [escape_result(*key, 24.0)] for key in compare.KERNELS}
    return {"on": on, "off": off}


def sites_for(kernels: list[str]) -> list[SiteReport]:
    """One eliminated Vec site per named kernel."""
    root = "portfolio.runtimeinternalslab.escape.EscapeCases."
    return [SiteReport(root + k, compare.VEC, f"EscapeCases.{k}@1", 1) for k in kernels]


FIXED = ["temporaries", "branchMergeFixed", "loopAccumulatorFixed", "staticStoreFixed"]


def test_escape_gates_pass_on_healthy_measurements() -> None:
    report, verdict = compare.escape_report(healthy(), sites_for(FIXED))
    assert verdict["problems"] == []
    assert verdict["summary"] == [
        "pairs_agree=yes",
        "fixed_zero_alloc=4/4",
        "escaping_still_allocate=3/3",
        "log_eliminations_in_fixed=4/4",
    ]
    assert "| branch-merge | fixed | 0.0 [0.0-0.0] | 24.0 [24.0-24.0] |" in report


def test_escape_gates_catch_each_kind_of_regression() -> None:
    m = healthy()
    m["on"][("branch-merge", "fixed")] = [escape_result("branch-merge", "fixed", 24.0)]
    m["on"][("static-store", "escapes")] = [escape_result("static-store", "escapes", 0.0)]
    m["off"][("loop-accumulator", "fixed")] = [escape_result("loop-accumulator", "fixed", 24.0, result=8)]
    _, verdict = compare.escape_report(m, sites_for(FIXED[:-1]))
    problems = "\n".join(verdict["problems"])
    assert "branch-merge fixed still allocates" in problems
    assert "static-store escapes allocated only" in problems
    assert "no eliminated Vec allocation logged for staticStoreFixed" in problems
    assert "different results" in problems
    assert "pairs_agree=no" in verdict["summary"]


def test_churn_table_reports_medians_ranges_and_missing_allocation_counts() -> None:
    def churn(runtime: str, ns: float, alloc: float | None) -> ChurnResult:
        return ChurnResult(runtime, "v", "vm", (), 0, 1_000_000, 42, 2, 4041745370, ns, alloc, 4, 2.0)

    table = compare.churn_table(
        {
            ("Java", 0): [churn("java", 3.0, 0.0), churn("java", 2.0, 0.0), churn("java", 4.0, 0.0)],
            ("CPython", 0): [churn("python", 1000.0, None)],
        }
    )
    assert "| Java | 0 | 3.0 [2.0-4.0] | 67% | 0.0 [0.0-0.0] | 2.0 [2.0-2.0] | 1.00 [1.00-1.00] | 4041745370 |" in table
    assert "| CPython | 0 | 1,000.0 [1,000.0-1,000.0] | 0% | not measured |" in table


def test_the_runner_refuses_a_folder_without_the_spec(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="not found"):
        compare.Lab(tmp_path)
