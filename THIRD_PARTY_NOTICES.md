# Third-party notices and dependency review

Project source is original GPL-3.0-or-later. No code from Ardour MCP or REAPER MCP peers was copied. Repository review and architecture inspiration are cited in RESEARCH.md. Ardour GPL-2.0-or-later is a separately installed application; its binaries, plugin code and documentation are not shipped in this package. LICENSE is the unmodified GPLv3 license text.

| Runtime dependency | Purpose | License | Essential / standard-library replacement | Maintenance evidence |
|---|---|---|---|---|
| mcp 2.3.x | Official MCP server/client protocol and transports | MIT | Essential; do not reimplement the protocol | Official stable 2.3.0 released 2026-10-02, inspected source/tag/PyPI; 2.2.0 also tested |
| pydantic 2.x | Typed request/result validation and JSON schemas | MIT | Essential; replacing it duplicates validation/schema maintenance | Current 2.13.5 installed and tested |
| numpy 2.x | Offline numeric audio buffers and statistics | BSD-3-Clause | Optional analysis; standard library impractical for dense audio | 2.5.3 tested |
| scipy 1.x | Welch spectrum, polyphase peak estimate | BSD-3-Clause and bundled third-party notices | Optional analysis; avoid custom DSP reimplementation | 1.18.1 tested |
| soundfile | libsndfile decoding and metadata | BSD-3-Clause | Optional analysis; wave alone cannot handle requested formats | 0.14.0 tested |
| libsndfile | Native audio codec dependency of SoundFile wheels | LGPL-2.1-or-later, codec dependencies have own licenses | Optional external/bundled wheel dependency; preserve upstream wheel notices | Supplied by SoundFile/platform; not vendored here |
| pyloudnorm | BS.1770-weighted integrated loudness | MIT | Optional analysis; independent fixtures validate levels, no certification claim | 0.2.0 tested |

The official SDK brings its maintained protocol/auth/types modules and HTTP/async dependencies even though this server exposes only STDIO. Their installed distributions retain their licenses; inspect the wheel dependency lock/inventory during release. Typical licenses include MIT (AnyIO, Pydantic core, JSONSchema), BSD-3-Clause (HTTPX, Starlette, Uvicorn), Apache-2.0/BSD dual (packaging). This file is not a substitute for notices contained in upstream dependency wheels.

Development-only dependencies: pytest MIT, pytest-asyncio Apache-2.0, pytest-cov MIT, coverage Apache-2.0, Ruff MIT, mypy MIT, build MIT, pip-audit Apache-2.0, Bandit Apache-2.0, Lupa MIT (Lua runtimes MIT). They are not required by the core server. Exact installed distribution versions are in artifacts/environment.json; vulnerability audit is artifacts/dependency-audit.json. No peer dependency or REAPER runtime is introduced.

Optional free plugin ecosystem: Ardour bundled LV2 processors, x42 plugins (GPL), LSP Plugins (LGPL/GPL component licenses), Calf (LGPL-2.1), DISTRHO/DPlug ecosystem (individual licenses), and Surge XT (GPL-3.0). Check each actual package's license/platform before redistribution. None is mandatory. Format support comes from the Ardour build and installed inventory, not an OS promise.
