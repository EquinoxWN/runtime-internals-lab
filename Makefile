.PHONY: setup lint test build bench escape audit ci

# PY is the Python to use (the repo's .venv locally, setup-python's in CI); MVNLOCAL (set by the
# author's repoenv helper) keeps the Maven repository inside the repo and is empty in CI.
PY ?= python
MVN = mvn -B -q $(MVNLOCAL)

setup:
	cd python && $(PY) -m pip install -e ".[dev]"
	cd js && npm ci

# Spotless check and javac -Xlint:all -Werror; ruff, ruff format and mypy --strict; tsc --checkJs --strict.
lint:
	cd java && $(MVN) -DskipTests compile
	cd python && $(PY) -m ruff check . && $(PY) -m ruff format --check . && $(PY) -m mypy
	cd js && npm run -s lint

# Every runtime against spec/workload.json, plus the escape-analysis checks inside the test JVM.
test:
	cd java && $(MVN) verify
	cd python && $(PY) -m pytest -q
	cd js && npm test

build:
	cd java && $(MVN) -DskipTests compile

# The shared workload in Java, Node.js and CPython: 5 fresh processes per configuration (about 2 min).
# Exits with 3 if any runtime's checksum differs from the spec.
bench: build
	$(PY) -m runtime_internals_lab.compare churn

# Escape analysis on and off, plus a -XX:+LogCompilation run read back by the Python log parser.
# Exits with 3 if a fixed variant allocates, an escaping one stops, or the log shows no elimination.
escape: build
	$(PY) -m runtime_internals_lab.compare escape

# Known vulnerabilities in Python, npm and Maven dependencies (Maven via OSV.dev, test scope included).
audit:
	cd python && $(PY) -m pip_audit --skip-editable --cache-dir ../.tmp/pip-audit
	cd js && npm audit --audit-level=low
	cd java && $(MVN) dependency:list -DincludeScope=test -DoutputFile=target/dependencies.txt
	$(PY) scripts/osv_audit.py Maven java/target/dependencies.txt

ci: setup lint test bench escape audit
