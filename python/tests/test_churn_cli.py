"""The CPython harness prints one valid result line and measures the cycle collector."""

from __future__ import annotations

import gc
import json

import pytest

from runtime_internals_lab.churn import main, same
from runtime_internals_lab.meter import GcMeter, runtime_info
from runtime_internals_lab.results import ChurnResult


def test_churn_prints_one_result_line_with_the_shared_checksum(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--ops", "1000", "--window", "10", "--seed", "42", "--warmup", "1", "--rounds", "2"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    result = ChurnResult.parse(lines[0])
    assert (result.runtime, result.checksum, result.rounds) == ("python", 1706363773, 2)
    assert result.alloc_bytes_per_op is None
    assert isinstance(json.loads(lines[0])["collectors"], dict)


def test_the_largest_seed_and_zero_warm_up_rounds_are_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--ops", "1000", "--window", "100", "--seed", "4294967295", "--warmup", "0", "--rounds", "1"]) == 0
    assert ChurnResult.parse(capsys.readouterr().out).checksum == 166371539


@pytest.mark.parametrize(
    "argv",
    [["--ops", "0"], ["--seed", "0"], ["--window", "1000001"], ["--ops", "1e3"], ["--nope", "1"], ["--op", "5"]],
)
def test_bad_arguments_exit_with_2(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 2
    assert capsys.readouterr().out == ""


def test_rounds_that_disagree_are_reported() -> None:
    assert same(-1, 5) == 5
    assert same(5, 5) == 5
    with pytest.raises(RuntimeError, match="checksum changed"):
        same(5, 6)


def test_the_gc_meter_times_every_collection_and_removes_its_callback() -> None:
    before = len(gc.callbacks)
    with GcMeter() as meter:
        gc.collect()
        gc.collect(0)
    assert meter.count >= 2
    assert meter.total_ns > 0
    assert meter.max_ns <= meter.total_ns
    assert sum(int(v["count"]) for v in meter.collectors().values()) == meter.count
    assert len(gc.callbacks) == before


def test_runtime_info_records_version_and_gc_settings() -> None:
    info = runtime_info()
    assert info["runtime"] == "python"
    assert any(f.startswith("gc.threshold=") for f in info["flags"])
    assert any(f.startswith("gil=") for f in info["flags"])
