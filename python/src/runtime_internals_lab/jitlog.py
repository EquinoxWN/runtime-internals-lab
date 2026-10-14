"""Reads HotSpot's `-XX:+LogCompilation` XML and lists the allocations C2 scalar-replaced.

C2 writes an `<eliminate_allocation type=...>` element, with the inlining stack of the `new`
bytecode as `<jvms bci=... method=...>` children, for every allocation its escape analysis
removed. Identifiers (`type`, `method`) are only valid inside the `<task>` that defines them.

usage: python -m runtime_internals_lab.jitlog LOG [--javap JAVAP_OUTPUT] [--only PACKAGE_PREFIX]
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

MAX_LOG_BYTES = 512 * 1024 * 1024
_HEAD_BYTES = 4096
_CHUNK_BYTES = 1 << 20


@dataclass(frozen=True)
class Frame:
    """One level of an inlining stack: a method and a bytecode index."""

    method: str
    bci: int


@dataclass(frozen=True)
class Elimination:
    """An allocation C2 removed: the allocated class and where the `new` was, innermost first."""

    type_name: str
    frames: tuple[Frame, ...]

    @property
    def site(self) -> Frame:
        """The `new` bytecode itself."""
        return self.frames[0]

    @property
    def root(self) -> Frame:
        """The compiled method the allocation was inlined into."""
        return self.frames[-1]


@dataclass
class Task:
    """One compilation: method, kind (normal or OSR), compiler tier, and what it eliminated."""

    compile_id: str
    method: str
    kind: str
    level: int | None
    success: bool = False
    eliminations: list[Elimination] = field(default_factory=list)
    inline_failures: list[tuple[str, str]] = field(default_factory=list)

    @property
    def is_c2(self) -> bool:
        """C2 tasks carry no `level` attribute in the log; C1 tasks have levels 1 to 3."""
        return self.level is None or self.level == 4


def _class_name(raw: str) -> str:
    """`java/lang/String` -> `java.lang.String`."""
    return raw.replace("/", ".")


def _task_method(raw: str) -> str:
    """`pkg.Cls name (II)J` -> `pkg.Cls.name`."""
    parts = raw.split(" ")
    return f"{_class_name(parts[0])}.{parts[1]}" if len(parts) >= 2 else raw


def _elements(parser: ET.XMLPullParser[ET.Element]) -> Iterator[tuple[str, ET.Element]]:
    """Pending start and end events (the only kinds requested) with their elements."""
    for item in parser.read_events():
        if len(item) == 2 and isinstance(item[1], ET.Element):
            yield item[0], item[1]


def _events(path: Path, max_bytes: int) -> Iterator[tuple[str, ET.Element]]:
    """Stream (event, element) pairs; refuse oversized files and any DTD, so no entity can expand."""
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"{path} is {size} bytes, above the {max_bytes}-byte limit")
    # The DTD check below runs on every chunk before it reaches the parser, and ElementTree never
    # fetches external resources, so the stdlib parser is safe for this input.
    parser: ET.XMLPullParser[ET.Element] = ET.XMLPullParser(events=("start", "end"))
    tail = b""
    first = True
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK_BYTES):
            window = tail + chunk
            if b"<!DOCTYPE" in window or b"<!ENTITY" in window:
                raise ValueError(f"{path} has a DOCTYPE or ENTITY declaration; not a HotSpot log")
            if first and b"<hotspot_log" not in chunk[:_HEAD_BYTES]:
                raise ValueError(f"{path} does not look like a -XX:+LogCompilation file")
            first = False
            tail = chunk[-16:]
            parser.feed(chunk)
            yield from _elements(parser)
    parser.close()
    yield from _elements(parser)


def parse(path: Path, max_bytes: int = MAX_LOG_BYTES) -> list[Task]:
    """Stream the log and return every compilation task with its eliminations."""
    tasks: list[Task] = []
    task: Task | None = None
    klasses: dict[str, str] = {}
    methods: dict[str, str] = {}
    pending: list[Frame] | None = None
    pending_type = ""
    last_call = ""
    for event, el in _events(path, max_bytes):
        tag = el.tag
        if event == "start":
            if tag == "task":
                level = el.get("level")
                task = Task(
                    compile_id=el.get("compile_id", "?"),
                    method=_task_method(el.get("method", "?")),
                    kind=el.get("compile_kind", "normal"),
                    level=int(level) if level and level.isdigit() else None,
                )
                klasses, methods = {}, {}
            elif task is None:
                continue
            elif tag in ("klass", "type"):
                klasses[el.get("id", "")] = _class_name(el.get("name", "?"))
            elif tag == "method":
                holder = klasses.get(el.get("holder", ""), "?")
                methods[el.get("id", "")] = f"{holder}.{el.get('name', '?')}"
            elif tag == "call":
                last_call = methods.get(el.get("method", ""), "?")
            elif tag == "inline_fail":
                task.inline_failures.append((last_call, el.get("reason", "?")))
            elif tag == "eliminate_allocation":
                pending = []
                pending_type = klasses.get(el.get("type", ""), "?")
            elif tag == "jvms" and pending is not None:
                pending.append(Frame(methods.get(el.get("method", ""), "?"), int(el.get("bci", "-1"))))
            elif tag == "task_done":
                task.success = el.get("success") == "1"
        else:
            if tag == "eliminate_allocation" and task is not None and pending is not None:
                if pending:
                    task.eliminations.append(Elimination(pending_type, tuple(pending)))
                pending = None
            elif tag == "task" and task is not None:
                tasks.append(task)
                task = None
            if tag in ("task", "compilation_log", "hotspot_log", "tty"):
                el.clear()
    return tasks


_JAVAP_CLASS = re.compile(r"^(?:[\w$]+\s+)*(?:class|interface|enum|record)\s+([\w.$]+)")
_JAVAP_METHOD = re.compile(r"^\s{2}(?:[\w$.<>\[\], ]+\s)?([\w$.]+)\(.*\);$")
_JAVAP_LINE = re.compile(r"^\s+line (\d+): (\d+)$")


def line_tables(javap_output: str) -> dict[str, list[tuple[int, int]]]:
    """Parse `javap -l -p` output into `class.method -> [(start_bci, line), ...]`."""
    tables: dict[str, list[tuple[int, int]]] = {}
    cls = ""
    current: list[tuple[int, int]] | None = None
    for raw in javap_output.splitlines():
        m = _JAVAP_CLASS.match(raw)
        if m:
            cls = m.group(1)
            current = None
            continue
        m = _JAVAP_METHOD.match(raw)
        if m and cls:
            name = m.group(1)
            simple = cls.rsplit(".", 1)[-1]
            if name in (cls, simple):
                name = "<init>"
            key = f"{cls}.{name}"
            # Overloaded names are ambiguous without descriptors: keep the first table only.
            current = [] if key not in tables else None
            if current is not None:
                tables[key] = current
            continue
        m = _JAVAP_LINE.match(raw)
        if m and current is not None:
            current.append((int(m.group(2)), int(m.group(1))))
    for entries in tables.values():
        entries.sort()
    return tables


def source_line(tables: dict[str, list[tuple[int, int]]], frame: Frame) -> int | None:
    """Source line of a bytecode index, or None when the method has no line table."""
    best = None
    for start, line in tables.get(frame.method, []):
        if start <= frame.bci:
            best = line
    return best


@dataclass(frozen=True)
class SiteReport:
    """One eliminated allocation site, aggregated over every C2 task that removed it."""

    root: str
    type_name: str
    chain: str
    tasks: int


def summarize(
    tasks: Iterable[Task], only: str = "", tables: dict[str, list[tuple[int, int]]] | None = None
) -> list[SiteReport]:
    """Distinct eliminated sites per root method, optionally limited to a package prefix."""
    counts: Counter[tuple[str, str, str]] = Counter()
    for t in tasks:
        if not (t.is_c2 and t.success):
            continue
        seen: set[tuple[str, str, str]] = set()
        for e in t.eliminations:
            if only and not e.root.method.startswith(only):
                continue
            chain = " <- ".join(_describe(f, tables or {}) for f in e.frames)
            key = (e.root.method, e.type_name, chain)
            if key not in seen:
                seen.add(key)
                counts[key] += 1
    return [SiteReport(root, typ, chain, n) for (root, typ, chain), n in sorted(counts.items())]


def _describe(frame: Frame, tables: dict[str, list[tuple[int, int]]]) -> str:
    """`Cls.method@bci (line N)` with the class name shortened to its simple name."""
    simple = frame.method.rsplit(".", 2)
    short = ".".join(simple[-2:]) if len(simple) >= 2 else frame.method
    line = source_line(tables, frame)
    return f"{short}@{frame.bci}" + (f" (line {line})" if line is not None else "")


def render(reports: Sequence[SiteReport]) -> str:
    """Markdown table of eliminated allocation sites."""
    rows = ["| Compiled method | Type removed | Allocation site, innermost first | C2 tasks |", "|---|---|---|---|"]
    rows += [
        f"| `{r.root.rsplit('.', 1)[-1]}` | `{r.type_name.rsplit('.', 1)[-1]}` | {r.chain} | {r.tasks} |"
        for r in reports
    ]
    return "\n".join(rows)


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point: print the eliminated allocations of a log."""
    p = argparse.ArgumentParser(prog="jitlog", allow_abbrev=False)
    p.add_argument("log", type=Path)
    p.add_argument("--javap", type=Path, help="output of `javap -l -p` for source line numbers")
    p.add_argument("--only", default="", help="keep compiled methods whose name starts with this prefix")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    tables = line_tables(args.javap.read_text(encoding="utf-8")) if args.javap else {}
    tasks = parse(args.log)
    reports = summarize(tasks, args.only, tables)
    c2 = sum(1 for t in tasks if t.is_c2)
    print(f"{len(tasks)} compilation tasks, {c2} by C2, {len(reports)} distinct eliminated allocation sites")
    print(render(reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
