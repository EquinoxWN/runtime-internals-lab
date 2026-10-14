# Contributing

Thanks for helping. This is a Java, Python and JavaScript project; issues and pull requests are welcome.

## Set up and check your change

Needs JDK 21+ with Maven 3.9+, Python 3.11+, Node.js 24+. Caches, virtual environments and
experiment output stay in git-ignored folders inside the repo (`.venv/`, `node_modules/`, `.tmp/`).

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make setup   # Python dev tools, npm packages
make lint    # Spotless + javac -Werror, ruff + mypy --strict, tsc --checkJs --strict
make test    # 99 tests across the three runtimes
make bench   # the shared workload in Java, Node.js and CPython (about 2 minutes)
make escape  # escape analysis on and off, read back from -XX:+LogCompilation (about 30 s)
make audit   # known-vulnerability check (as in CI)
```

`cd java && mvn spotless:apply` formats the Java sources. A pull request is ready when
`make lint` and `make test` pass and CI is green.

## Guidelines

- A change to the workload must keep all three implementations in step: update
  `spec/workload.json` and every suite's checksum test together.
- New experiments print one JSON line per measurement, and the Python runner validates them; keep
  every file a JVM writes under `.tmp/` and every heap capped.
- Report numbers with the machine, versions, flags and the spread over repeated runs, and update
  `docs/results/` when numbers change.
- Significant design changes need an ADR in `docs/adr/` (copy `0001` for the format).
- Keep function comments to one short phrase; let names and tests explain the rest.
- Report security problems privately, as described in [SECURITY.md](SECURITY.md).

By contributing you agree that your work is released under the [MIT License](LICENSE).
