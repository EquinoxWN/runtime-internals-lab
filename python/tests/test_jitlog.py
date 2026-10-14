"""The LogCompilation reader finds the allocations C2 removed, using a trimmed real JDK 21 log."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime_internals_lab import jitlog

ESCAPE_CASES = "portfolio.runtimeinternalslab.escape.EscapeCases"
VEC = "portfolio.runtimeinternalslab.workload.Vec"
RNG = "portfolio.runtimeinternalslab.workload.XorShift32"


@pytest.fixture
def tasks(fixtures: Path) -> list[jitlog.Task]:
    """Three tasks from a real run: C2 for both branch-merge variants, C1 for the fixed one."""
    return jitlog.parse(fixtures / "escape-compilation.xml")


def test_tasks_are_read_with_their_method_kind_and_tier(tasks: list[jitlog.Task]) -> None:
    assert [(t.compile_id, t.method, t.kind, t.is_c2, t.success) for t in tasks] == [
        ("465", f"{ESCAPE_CASES}.branchMergeEscapes", "normal", True, True),
        ("474", f"{ESCAPE_CASES}.branchMergeFixed", "normal", True, True),
        ("471", f"{ESCAPE_CASES}.branchMergeFixed", "normal", False, True),
    ]


def test_the_merged_allocation_is_not_eliminated_but_the_fixed_one_is(tasks: list[jitlog.Task]) -> None:
    escapes, fixed, _ = tasks
    assert [e.type_name for e in escapes.eliminations] == [RNG]
    assert sorted(e.type_name for e in fixed.eliminations) == [VEC, RNG]
    vec = next(e for e in fixed.eliminations if e.type_name == VEC)
    assert vec.site == jitlog.Frame(f"{ESCAPE_CASES}.branchMergeFixed", 64)
    assert vec.root == vec.site


def test_c1_tasks_are_skipped_and_sites_map_to_source_lines(tasks: list[jitlog.Task], fixtures: Path) -> None:
    tables = jitlog.line_tables((fixtures / "javap-escape-cases.txt").read_text(encoding="utf-8"))
    sites = jitlog.summarize(tasks, f"{ESCAPE_CASES}.", tables)
    assert [(s.root.rsplit(".", 1)[-1], s.type_name.rsplit(".", 1)[-1], s.chain, s.tasks) for s in sites] == [
        ("branchMergeEscapes", "XorShift32", "EscapeCases.branchMergeEscapes@0 (line 64)", 1),
        ("branchMergeFixed", "Vec", "EscapeCases.branchMergeFixed@64 (line 94)", 1),
        ("branchMergeFixed", "XorShift32", "EscapeCases.branchMergeFixed@0 (line 81)", 1),
    ]
    assert jitlog.summarize(tasks, "java.") == []
    assert "| `branchMergeFixed` | `Vec` |" in jitlog.render(sites)


def test_javap_line_tables_cover_methods_and_constructors(fixtures: Path) -> None:
    tables = jitlog.line_tables((fixtures / "javap-escape-cases.txt").read_text(encoding="utf-8"))
    assert f"{VEC}.<init>" in tables
    assert f"{VEC}.add" in tables
    frame = jitlog.Frame(f"{ESCAPE_CASES}.branchMergeEscapes", 94)
    assert jitlog.source_line(tables, frame) == 66
    assert jitlog.source_line(tables, jitlog.Frame("x.Y.z", 0)) is None


def test_document_type_declarations_are_refused(tmp_path: Path) -> None:
    bomb = tmp_path / "bomb.xml"
    bomb.write_text(
        '<?xml version="1.0"?>\n<!DOCTYPE hotspot_log [<!ENTITY a "aaaa">]>\n<hotspot_log>&a;</hotspot_log>\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="DOCTYPE"):
        jitlog.parse(bomb)


def test_other_files_and_oversized_logs_are_refused(tmp_path: Path, fixtures: Path) -> None:
    other = tmp_path / "other.xml"
    other.write_text("<root/>", encoding="utf-8")
    with pytest.raises(ValueError, match="LogCompilation"):
        jitlog.parse(other)
    with pytest.raises(ValueError, match="limit"):
        jitlog.parse(fixtures / "escape-compilation.xml", max_bytes=100)


def test_the_command_line_prints_a_table(fixtures: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = str(fixtures / "escape-compilation.xml")
    javap = str(fixtures / "javap-escape-cases.txt")
    assert jitlog.main([log, "--javap", javap, "--only", f"{ESCAPE_CASES}."]) == 0
    out = capsys.readouterr().out
    assert out.startswith("3 compilation tasks, 2 by C2, 3 distinct eliminated allocation sites")
    assert "EscapeCases.branchMergeFixed@64 (line 94)" in out


def test_ids_are_scoped_to_the_task_that_declares_them(tmp_path: Path) -> None:
    log = tmp_path / "two-tasks.xml"
    log.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n<hotspot_log version='160 1'>\n<compilation_log thread='1'>\n"
        "<task compile_id='1' method='a.A f ()V'><klass id='7' name='a/Box'/><method id='8' holder='7' name='f'/>"
        "<eliminate_allocation type='7'><jvms bci='3' method='8'/></eliminate_allocation>"
        "<task_done success='1'/></task>\n"
        "<task compile_id='2' method='a.A g ()V'>"
        "<eliminate_allocation type='7'><jvms bci='5' method='8'/></eliminate_allocation>"
        "<task_done success='1'/></task>\n</compilation_log>\n</hotspot_log>\n",
        encoding="utf-8",
    )
    first, second = jitlog.parse(log)
    assert first.eliminations == [jitlog.Elimination("a.Box", (jitlog.Frame("a.Box.f", 3),))]
    assert second.eliminations == [jitlog.Elimination("?", (jitlog.Frame("?", 5),))]
