"""The spec loader and the result-line parser reject anything that does not match exactly."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from runtime_internals_lab.results import ChurnResult, EscapeResult, ProbeResult, summarize
from runtime_internals_lab.spec import Spec, parse_spec

JAVA_LINE = (
    '{"runtime":"java","version":"21.0.12.1+1-LTS","vm":"OpenJDK 64-Bit Server VM","flags":["-Xmx512m"],'
    '"max_heap_bytes":536870912,"workload":"vector-churn","ops":1000000,"window":0,"seed":42,"warmup":20,'
    '"rounds":20,"checksum":4041745370,"wall_ns":56000000,"ns_per_op":2.8000,"alloc_bytes":0,'
    '"alloc_bytes_per_op":0.0000,"gc_count":0,"gc_time_ms":0.0000,"collectors":{"G1 Young Generation":'
    '{"count":0,"time_ms":0}}}'
)
ESCAPE_LINE = (
    '{"runtime":"java","version":"21","vm":"OpenJDK","flags":[],"max_heap_bytes":1,"experiment":"escape",'
    '"case":"branch-merge","variant":"fixed","ops":1000,"seed":42,"warmup":1,"rounds":1,"result":5,'
    '"agrees":true,"wall_ns":10,"ns_per_op":0.01,"alloc_bytes":0,"alloc_bytes_per_op":0.0,"gc_count":0,'
    '"gc_time_ms":0.0}'
)


@pytest.fixture
def raw_spec(repo: Path) -> dict[str, Any]:
    """The spec file as plain JSON (a fresh copy per test)."""
    data: dict[str, Any] = json.loads((repo / "spec" / "workload.json").read_text(encoding="utf-8"))
    return data


def test_the_shared_spec_loads_and_answers_checksum_lookups(spec: Spec) -> None:
    assert spec.bench.windows == (0, 100_000)
    assert spec.expected_checksum(1_000_000, 0, 42) == 4041745370
    assert spec.expected_checksum(3, 0, 42) is None
    assert set(spec.bench.rounds) == {"java", "node", "python"}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("name",), "other"),
        (("version",), 2),
        (("checksums", 0, "checksum"), 2**32),
        (("checksums", 0, "ops"), True),
        (("checksums", 0, "seed"), 0),
        (("bench", "repeats"), 0),
        (("bench", "windows"), []),
        (("xorshift32", 0, "first"), []),
    ],
)
def test_spec_validation_rejects_bad_values(path: tuple[Any, ...], value: Any, raw_spec: dict[str, Any]) -> None:
    data = copy.deepcopy(raw_spec)
    target: Any = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match=r"spec|vector|list|xorshift"):
        parse_spec(data)


def test_spec_validation_requires_rounds_for_every_runtime(raw_spec: dict[str, Any]) -> None:
    data = raw_spec
    del data["bench"]["rounds"]["node"]
    with pytest.raises(ValueError, match="java, node and python"):
        parse_spec(data)


def test_result_lines_from_every_harness_shape_parse() -> None:
    java = ChurnResult.parse(JAVA_LINE)
    assert (java.runtime, java.checksum, java.measured_ops, java.alloc_bytes_per_op) == (
        "java",
        4041745370,
        20_000_000,
        0.0,
    )
    escape = EscapeResult.parse(ESCAPE_LINE)
    assert (escape.case, escape.variant, escape.agrees) == ("branch-merge", "fixed", True)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"extra": 1}, "unexpected"),
        ({"checksum": "1"}, "wrong type"),
        ({"rounds": True}, "boolean"),
        ({"rounds": 0}, "positive"),
        ({"ops": 0}, "positive"),
        ({"gc_count": -1}, "positive"),
        ({"workload": "other"}, "vector-churn"),
        ({"checksum": 2**32}, "32-bit"),
        ({"flags": [1]}, "strings"),
    ],
)
def test_malformed_result_lines_are_rejected(change: dict[str, Any], message: str) -> None:
    data = json.loads(JAVA_LINE)
    data.update(change)
    with pytest.raises(ValueError, match=message):
        ChurnResult.parse(json.dumps(data))


def test_missing_fields_oversized_lines_and_non_objects_are_rejected() -> None:
    data = json.loads(JAVA_LINE)
    del data["gc_count"]
    with pytest.raises(ValueError, match="missing"):
        ChurnResult.parse(json.dumps(data))
    with pytest.raises(ValueError, match="too long"):
        ChurnResult.parse(" " * 70_000)
    with pytest.raises(ValueError, match="not a JSON object"):
        ChurnResult.parse("[1]")
    bad = json.loads(ESCAPE_LINE)
    bad["variant"] = "other"
    with pytest.raises(ValueError, match="escape"):
        EscapeResult.parse(json.dumps(bad))


def test_summaries_report_median_range_and_spread() -> None:
    s = summarize([3.0, 1.0, 2.0, 10.0])
    assert (s.median, s.low, s.high, s.n) == (2.5, 1.0, 10.0, 4)
    assert s.spread == pytest.approx(3.6)
    assert s.fmt(1) == "2.5 [1.0-10.0]"
    assert summarize([0.0]).spread == 0.0
    with pytest.raises(ValueError, match="nothing"):
        summarize([])


def test_v8_probe_lines_parse_and_unknown_kernels_are_rejected() -> None:
    line = (
        '{"runtime":"node","version":"v24.19.0","vm":"V8 13.6","flags":["--max-old-space-size=512"],'
        '"max_heap_bytes":738197504,"experiment":"v8-escape","kernel":"inline","ops":1000000,"rounds":10,'
        '"result":393199325142,"agrees":true,"ns_per_op":3.8,"alloc_bytes_per_op":0.0003,"gc_count":0}'
    )
    probe = ProbeResult.parse(line)
    assert (probe.kernel, probe.agrees, probe.alloc_bytes_per_op) == ("inline", True, 0.0003)
    with pytest.raises(ValueError, match="V8 escape-probe"):
        ProbeResult.parse(line.replace('"inline"', '"other"'))
