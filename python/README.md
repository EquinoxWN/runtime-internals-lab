# Python package: runtime_internals_lab

Two roles: the CPython version of the shared workload, and the tools that run and check every
runtime.

| Module | What it does |
|---|---|
| `xorshift`, `workload` | xorshift32 and the vector-churn workload (`spec/workload.md`), CPython version |
| `meter`, `churn` | cycle-collector timing with `gc.callbacks`; `python -m runtime_internals_lab.churn` prints one JSON result line |
| `spec`, `results` | strict loaders for `spec/workload.json` and for the result lines every harness prints |
| `jitlog` | reads HotSpot `-XX:+LogCompilation` XML and lists the allocations C2 removed, with source lines from `javap -l` |
| `compare` | `python -m runtime_internals_lab.compare churn` and `... escape`: runs the experiments in fresh processes, checks them and prints Markdown tables |

Run from the repository root after `make setup` (see the main [README](../README.md)).
