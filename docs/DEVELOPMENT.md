# Development

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e '.[analysis,dev]'
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/mypy src
.venv/bin/mypy src --platform win32
.venv/bin/mypy src --platform darwin
.venv/bin/pytest --cov=ardour_ultra_mcp --cov-branch
.venv/bin/python scripts/generate_reference.py
.venv/bin/python scripts/benchmark.py
.venv/bin/python -m build
```

Use equivalent `.venv\Scripts\` executables on Windows. No secrets/network are required at runtime. Dependency installation and research use the network.

Check explicit mypy target platforms when changing platform-dependent code. Its platform narrowing recognizes `sys.platform` guards; runtime-only `os.name` guards can cause Windows checks to inspect unavailable POSIX APIs. Target-platform checking does not replace native OS tests.

CI upgrades its runner packaging tools before auditing the environment. Python 3.11 runners initially supplied vulnerable setuptools 79.0.1; `setuptools>=83.0.0` resolves the reported PYSEC-2026-3447 advisory without suppressing `pip-audit`. Setuptools is CI tooling, not a server runtime dependency or the project's Hatchling build backend.

A new command needs: typed request with units, catalog entry, service preflight/policy, real allowlisted bridge handler with registered binding evidence, simulator behavior, failure/stale/batch tests and runtime validation status. Do not add a tool solely because a method exists in C++ or a peer README. Capabilities must distinguish missing bindings and unsupported workflows. Reuse code only after license review and attribution; current source is original.

Source evidence is pinned in research/sources.json; scripts/research_inventory.py reads external clones and should not alter pins casually. Runtime protocols are versioned separately from package semantic version. Prefer capability tests over scattered version comparisons. Native API additions can be isolated in adapters when actual differences justify it.

Generated TOOL_REFERENCE.md/tool-schemas.json derive from the catalog; `--check` detects drift. Keep client examples and status synchronized. Tests use the official SDK in-process and over actual subprocess STDIO. Actual Ardour scripts create disposable sessions, do not attach to user work, and retain evidence in artifacts.

No separate service class per requested domain is mandated prematurely; split current modules when new adapters increase responsibility. The Lua factory is intentionally self-contained for Ardour bytecode persistence. Do not move needed functions into unpersisted globals.

CI enforces an 80% combined Python coverage floor to catch major regressions. This is a floor, not the requested near-complete critical-path target; retain meaningful native failure/identity tests and raise the target as gaps close.
