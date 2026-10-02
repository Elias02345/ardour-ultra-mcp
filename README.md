# Ardour Ultra MCP

Local, open source, typed production primitives for Ardour through Model Context Protocol. Uses the official MCP Python SDK v2, Ardour Lua APIs and optional native OSC. No cloud APIs, proprietary model dependency or GUI automation.

**Development release — platform and feature verification is still in progress.** Read [implementation status](docs/IMPLEMENTATION_STATUS.md) and [compatibility](docs/COMPATIBILITY.md). The simulator is not evidence of real DAW support.

Install from this checkout (the package is not published to PyPI):

```sh
uv tool install '.[analysis]'
ardour-ultra-mcp install --ardour-major 9
ardour-ultra-mcp doctor --json
```

Activate the installed EditorHook in Ardour's Script Manager, then run `test-connection`. The installer prints the exact UI step and mailbox location. Native OSC is optional and disabled by default.

```sh
ardour-ultra-mcp configure claude
ardour-ultra-mcp configure codex
ardour-ultra-mcp serve --backend fake  # deterministic simulator, no audio engine
```

The server provides precise track, region, MIDI, plugin, routing, automation, transport and preset-based master export primitives. Capabilities distinguish implemented operations, runtime availability and remaining gaps. Each tool has a typed request, explicit units and structured outcomes/errors. Audio analysis is optional and runs outside Ardour.

Private mailbox IPC, allowlisted commands, explicit media/export roots, guarded note references, preflight and uncertain-outcome errors are integral to the design. Native undo exists only where Ardour exposes proper command objects. General ACID transactions, full human-edit revision tracking, stems and several deeper APIs are not yet available.

See [research](docs/RESEARCH.md), [architecture decision](docs/ARCHITECTURE_DECISION.md), and [tool reference](docs/TOOL_REFERENCE.md). GPL-3.0-or-later. Original implementation; no peer project code copied.
