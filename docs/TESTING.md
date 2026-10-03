# Testing and measured evidence

Initial development-release validation date: 2026-10-02. Hosted CI follow-up: 2026-10-03, recorded below. SDK 2.3.0 was published during initial development; its official tag/PyPI metadata were checked and Python/protocol tests repeated with that stable release. Native binding scripts exercise the backend directly; their results are not branded client application tests.

## Initial local results, 2026-10-02

| Check | Result / scope |
|---|---|
| Ruff lint | Passed; all project Python |
| Ruff format check | Passed |
| mypy strict | Passed, 32 source modules |
| Generated reference/schema drift | Passed |
| pytest, Python 3.12.14, MCP 2.3.0 | **112 passed**, 11.41 seconds with coverage |
| pytest, Python 3.14.8, MCP 2.3.0 | **112 passed**, 8.24 seconds, Linux container |
| Actual subprocess STDIO | Official Client auto/current discovery and legacy negotiation; typed tools/results/errors and actual 10,000-note/point STDIO batches; included in pytest and clean wheel validation |
| Ardour 8.12 LuaSession | **39 checks passed**, actual libraries/Dummy session |
| Ardour 9.8.0~ds LuaSession | **47 checks passed**, actual libraries/Dummy session |
| Ardour 9.8 EditorHook | **74 checks passed**, actual editor on Xvfb/Dummy; no synthetic GUI input |
| Clean wheel installation | 7 grouped checks: CLI doctor/capabilities/status/test-connection, packaged Lua/Unicode install, official Client auto/legacy STDIO with discovery/mutation/readback/errors/offline analysis |
| Bandit | Zero reported findings; two documented suppressions for fixed Ardour executable version probing, not general shell tools |
| pip-audit | Zero known dependency vulnerabilities at scan time; unpublished local package skipped by the advisory database |
| Isolated package build | Wheel and sdist successfully built; packaged Lua/license inspected |
| macOS / Windows / hosted Actions | **Not executed**; source/path branches and CI configurations do not prove DAW support |

The editor harness also launches the real MCP STDIO server against its live private Lua mailbox. Eight checks exercise that complete path, including a −12 dB master-gain change, re-render/analysis and a measured comparison (peak −11.998 dB; integrated LUFS −12.000). It selects the source-verified bundled WAV preset without normalization for this test. Native checks include expected denials and readback assertions, not only successful mutations. Source pins and environments are in research/ and artifacts/environment.json. Exact native outcomes/timing: [8.12](../artifacts/ardour8-luasession-e2e.json), [9.8 common](../artifacts/ardour9-luasession-e2e.json), [9.8 editor](../artifacts/ardour-editor-e2e.json). Temporary audio/session paths in reports refer to disposable fixtures removed after testing.

## Coverage

Initial Python statements: **88.30%** (1547/1752). Branches: **73.64%** (461/626). Coverage.py's combined statement/branch figure: **84.44%**. This is not 100%, and the requested near-complete critical-path target remains unfinished. Lua is exercised through actual Lua decoder/fault tests and native binding fixtures; it is not included in Python coverage. Subprocess package startup is tested but not combined into Python coverage.

Generated local reports: artifacts/coverage.json, coverage.xml, coverage-html/index.html, pytest.xml. Reports are generated outputs; only compact validation summaries/evidence are versioned. Critical tests include stale revisions, exact note guards, undo/rollback, current-operation compensation failure, symlink/traversal/count limits, conflicting mailbox slot ownership, correlation/epoch/deadline/timeouts, allowlist/malformed JSON, dense automation preservation/zero anchor, canonical native IDs before PBD conversion, idempotent bus collisions and render-analysis stage failure.

## Hosted CI follow-up, 2026-10-03

[Run 37113646478](https://github.com/Elias02345/ardour-ultra-mcp/actions/runs/37113646478) passed all **12** Python/MCP jobs for commit `e0ba69caa891b3a47183ae96d9edfdeec2305626`: Ubuntu, macOS and Windows, each with Python 3.11, 3.12, 3.13 and 3.14. Checks include lint, formatting, strict types, generated-reference drift, branch coverage, Bandit, dependency audit, package build and simulator CLI startup. Compact evidence is in [ci-validation.json](../artifacts/ci-validation.json).

The initial hosted run exposed Windows type guards and vulnerable runner-provided setuptools 79.0.1. After those fixes, Windows tests additionally exposed installer newline/hash mismatch and a test client reusing old Lua replies. Installer publication now uses exact UTF-8 bytes. Lua test clients follow the real MailboxBackend's consumed-reply cleanup and unique correlation IDs. Regression tests simulate Windows newline conversion and non-replacing rename behavior on Linux. The native Windows heartbeat replacement gap remains open; passing these protocol fixtures does not resolve it.

| Hosted platform | Python versions | Test result | Representative combined coverage, Python 3.11 |
|---|---|---|---|
| Ubuntu | 3.11–3.14 | 114 passed per job | 84.45% |
| macOS | 3.11–3.14 | 114 passed per job | 84.75% |
| Windows | 3.11–3.14 | 113 passed, 1 skipped per job | 84.71% |

The Windows skip covers unprivileged symlink policy. All jobs retained security audits and the 80% coverage floor; no advisory was ignored. Setuptools was upgraded to a patched release before the audit. The unpublished local project is still skipped by the dependency advisory database.

Locally, Python 3.11.16 passed the updated **114-test** suite in 10.81 seconds. Statement coverage was **88.31%** (1549/1754), branch coverage **73.64%** (461/626), combined **84.45%**. Linux/macOS/Windows target-platform mypy checks passed, as did lint/format/reference/Bandit/audit/build checks. Native Ardour checks were not repeated for these Python installer/type/test changes. The optional hosted native-Ardour job was skipped because this was a push, not workflow_dispatch. Hosted runners do not certify Windows 11, Apple Silicon DAW integration, audio hardware or branded MCP clients.

## Reproduce pure Python checks

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[analysis,dev]'
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python scripts/generate_reference.py --check
.venv/bin/pytest --cov=ardour_ultra_mcp --cov-branch --cov-report=term --cov-report=json:artifacts/coverage.json --cov-report=xml:artifacts/coverage.xml --cov-report=html:artifacts/coverage-html --junitxml=artifacts/pytest.xml
.venv/bin/bandit -r src -f json -o artifacts/bandit.json
.venv/bin/pip-audit --format json --output artifacts/dependency-audit.json
.venv/bin/python scripts/benchmark.py
.venv/bin/python -m build
```

Use `.venv\Scripts\python.exe` and equivalent executables on Windows. Target-platform mypy checks and runner packaging requirements are documented in DEVELOPMENT.md. Network is used for dependency installation/audit, not server operation. No paid APIs/accounts.

Clean installation of the built wheel with the analysis extra:

```sh
uv venv /absolute/clean-env
uv pip install --python /absolute/clean-env/bin/python 'dist/ardour_ultra_mcp-0.1.0-py3-none-any.whl[analysis]'
/absolute/clean-env/bin/python scripts/validate_install.py artifacts/clean-install.json
```

The validation script asserts that imports resolve inside the clean environment, not the editable source tree. It runs the installed module and official MCP Client without pytest/development dependencies.

## Reproduce actual Ardour integration

Use only disposable sessions. The core harness starts Ardour's official LuaSession executable, creates its own Dummy session and runs the same installed allowlisted factory in the non-realtime loop. It does not attach to an existing user's GUI session. On a distribution package with Ardour 9 under /usr/lib/ardour9:

```sh
export ARDOUR_LUA_PATH=/usr/lib/ardour9/luasession
export ARDOUR_DLL_PATH=/usr/lib/ardour9
export ARDOUR_DATA_PATH=/usr/share/ardour9
export ARDOUR_CONFIG_PATH=/etc/ardour9
export LD_LIBRARY_PATH=/usr/lib/ardour9
export LV2_PATH=/usr/lib/lv2:/usr/lib/ardour9/LV2
.venv/bin/python scripts/run_ardour_e2e.py
```

Adapt paths to the actual installation. The 8.12 test used extracted Debian libraries with the equivalent ardour8/data/config/library paths, not an assumption that every distribution has these directories. Need a real available LV2 effect for the plugin fixture. The native GUI harness additionally needs the actual editor executable, Xvfb and a Lua signal header from the **same source version/build**:

```sh
export ARDOUR_GUI_PATH=/usr/lib/ardour9/ardour-9.8.0~ds
export ARDOUR_SIGNALS_PATH=/absolute/ardour-9.8/gtk2_ardour/luasignal_syms.inc.h
export XVFB_PATH=/usr/bin/Xvfb
export ARDOUR_MAJOR=9
.venv/bin/python scripts/run_ardour_gui_e2e.py
```

It uses isolated XDG config/home/session/export directories, creates a sine-wave audio fixture **offline before opening the GUI session**, and installs a trusted source-matched callback through Ardour's official persisted Lua format. That fixture construction is not a production audio-import adapter. Subsequent edits are real live Lua APIs. No mouse coordinates, key injection or image recognition. Xvfb is a virtual display, not input automation. Tests exercise actual MIDI model commands, 100/10,000-note inserts, guarded edit/delete, independent copies, audio region edits/fades/locks, native undo/redo, dense automation/undo, generic LV2/instrument insertion/parameters, groups/sends, transport readback, preset master export and real analysis/compare/render-and-analyze. The default CD preset normalizes, so it can mask a gain change: export results warn about preset settings and the test explicitly selects an unnormalized preset.

`tests/integration/Dockerfile` supplies a Debian sid source-independent binary test environment; recorded image includes Ardour 1:9.8.0+ds-1. The Dockerfile requires a trusted CA bundle through the `system_ca` BuildKit secret, e.g. `docker build --secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt -f tests/integration/Dockerfile -t ardour-ultra-e2e .`. Include your trusted proxy CA if required; never disable TLS checks. The local validation container used Python 3.14.8 and a separately installed package/test environment. Installed distribution versions can change: always record `luasession -V`, source-matched signal header and final artifact metadata. Do not call a different distribution package 9.8 merely because the fixture filename contains 9.8.

## Performance

Simulator measurements include content revision hashing, validation and undo snapshots. They do not predict real DAW latency. Large operations have only one measured iteration; small-query repetitions are limited. Concurrent system load and the actual machine affect results.

| Simulator workload | Iterations | Median ms | Maximum ms |
|---|---|---|---|
| simple_state_query | 10 | 0.025 | 0.052 |
| single_parameter_change | 10 | 0.114 | 0.246 |
| insert_100_midi_notes | 1 | 2.586 | 2.586 |
| insert_10000_midi_notes | 1 | 191.845 | 191.845 |
| create_10000_automation_points | 1 | 203.360 | 203.360 |
| enumerate_102_tracks | 3 | 14.357 | 20.216 |
| state_refresh_session | 3 | 21.871 | 24.269 |
| plugin_parameter_enumeration | 3 | 12.647 | 12.855 |

Native 9.8 editor observations, including mailbox/timer/validation/native execution (single observed calls, not a statistical latency guarantee): **100-note insert 103.319 ms**, **10,000-note insert 2602.670 ms**, **10,000 retained automation points 10963.094 ms**. The automation operation occupies the UI context; not the realtime audio callback. Real-time audio/thread profiling, cancellations and 100+ track native stress testing remain gaps. Peak/plugin/state calls generally incur the hook's 100ms polling period; inspect every actual call in the native report rather than extrapolating simulator times.

[Architecture prototype](../artifacts/architecture-prototype.json) measured synthetic UDP echo median 0.018287 ms and a 100ms-period synthetic mailbox median 102.821127 ms. These are transport-only figures. [Simulator benchmark](../artifacts/benchmarks.json) contains exact samples above. They justify dense batches, not end-to-end DAW claims.

## Findings and external verification

Native 9.8 OSC queries reply but can differ from Lua state after locate; both this codec and liblo submitted locate without moving the tested Dummy playhead. Root cause remains unverified. Queries report reply_received with state_verified=false; Lua is authoritative. Preserved [probe](../artifacts/osc-transport-probe.json) predates the conservative adapter flags, so its historical confirmed flag is not a current guarantee.

Detected and corrected during native testing: typed empty RouteGroup ABI difference, group registration/empty-group removal, Stateful IDs, MIDI note construction limits, whole-file playlist copy identity, dense automation coalescing and heartbeat refresh after long operations. Marker mutation is disabled after a Location ID probe returned zero. A scan with no reported vulnerabilities is not a complete independent security audit. Residual Windows DACL/file-IO proof, scoped human-edit revisions, UI blocking/realtime profiling and broader native failure tests are explicit gaps. See SECURITY.md, COMPATIBILITY.md and FINAL_GAP_ANALYSIS.md.

## Onboarding validation, 2026-10-03

The README/install/client/troubleshooting guides were reorganized, a German installation guide added and the CLI gained readable default diagnostics. Automation uses `--json`; configure snippets and MCP STDIO keep their existing formats. Ardour menu/sandbox guidance was corrected against source; this was not a repeated native GUI test.

Local Linux Python 3.12.14: **126 tests passed in 9.58 seconds**. Combined Python coverage **85.07%**, statements **89.08%** (1615/1813), branches **73.93%** (482/652). Ruff lint/format, strict mypy for Linux/Windows/macOS (33 modules), generated reference drift, local Markdown file links and package build passed. Bandit reported zero findings; pip-audit reported zero known vulnerabilities, with the unpublished local package skipped as before.

The documented public GitHub ZIP requirement with `[analysis]` and `--python 3.12` installed in isolated uv tool directories on Linux. A fresh wheel environment passed the existing **7 grouped validation checks**, including official Client current/legacy STDIO with dense MIDI/automation and real offline audio analysis. Another **5 grouped checks** verified readable install/uninstall guidance, Unicode/spaces paths, token exclusion, actionable missing-hook errors with exit code 2, simulated labels, preserved JSON and generated absolute client commands. Reports: `artifacts/onboarding-validation.json`, `artifacts/onboarding-clean-install.json`, `artifacts/onboarding-cli-install.json`.

uv bootstrap installers, branded clients, native macOS/Windows installations and the conditional Lua sandbox config remedy were not executed. Native Ardour E2E was not repeated because the bridge command implementation did not change. Existing native evidence remains separate. The local documentation checker validates file targets, not remote URLs or heading anchors. Hosted evidence above refers to its named historical run; use the README CI badge for the latest checks.
