# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub:
**Security > Report a vulnerability** on this repository
(`https://github.com/EquinoxWN/runtime-internals-lab/security/advisories/new`). Do not open a public issue.

Include what you found, how to reproduce it, and the impact you expect. You will get an answer
within 7 days. Fixes are released as soon as they are ready, and you are credited unless you ask
not to be.

## Supported versions

This project is pre-1.0. Only the latest commit on `main` receives fixes.

## Scope

- **In scope:** the log reader (`jitlog`) accepting a crafted file that expands entities, reads
  outside the given path or exhausts memory; the experiment runner executing anything other than
  the fixed `java`, `node` and `python` commands; experiments writing files outside the
  repository's `.tmp/` folder; result lines that bypass validation.
- **Out of scope:** performance differences between machines or JDK, Node.js and Python versions;
  those are measurements, not vulnerabilities.

## How this repository protects itself

- No runtime dependencies in any language; test and lint tools are pinned and audited.
- The runner starts processes with fixed argument lists (no shell), caps every JVM at
  `-Xmx512m` and Node.js at `--max-old-space-size=512`, and points crash files, heap dumps and
  temp files into `.tmp/`; a unit test checks this for every JVM launch.
- `jitlog` refuses files over 512 MiB and any `DOCTYPE` or `ENTITY` declaration before parsing;
  all harnesses reject unknown, repeated and out-of-range options.
- Every GitHub Action is pinned to a full commit SHA, and workflows run with read-only
  permissions and without persisted credentials.
- Dependabot update pull requests are paused (`open-pull-requests-limit: 0`) so the repository keeps a single `main` branch; dependencies are updated by hand and checked by the CI audit.
- CI runs lint, tests and a known-vulnerability check (pip-audit, npm audit, and OSV.dev for the
  Maven dependencies) on every push and pull request.
