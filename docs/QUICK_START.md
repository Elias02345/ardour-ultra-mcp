# Quick start

Install from this checkout; no public package release is claimed:

```sh
uv tool install '.[analysis]'
# Alternative: pipx install '.[analysis]'
ardour-ultra-mcp install --ardour-major 9
```

In Ardour, open a disposable session first. Add **Ardour Ultra MCP** in Window → Scripting → Script Manager → Action Hooks. This is an EditorHook, never a DSP/Session realtime script. File IPC requires **Sandbox all Lua scripts** to be disabled in scripting preferences; review the installed script and activate it only on trusted projects. The installer does not silently weaken Ardour preferences.

```sh
ardour-ultra-mcp test-connection --json
ardour-ultra-mcp doctor --json
ardour-ultra-mcp capabilities --json
ardour-ultra-mcp configure claude
ardour-ultra-mcp configure codex
```

Configure your client using [installation](INSTALLATION.md). All tools accept `{"request": {...}}`; the following are request payloads, not shell commands:

```json
{"name":"Bass","kind":"midi","channels":2,"dry_run":true}
```

Inspect capabilities before executing `create_track`. Retain the returned `data.id`; use it as `track_id` for `set_track_gain` with `gain_db: -4.25` and `set_track_pan` with `pan: -0.35`. Verify with `get_track`. Pan is signed normalized azimuth, not a physical angle or surround panner.

For MIDI, read [MIDI](MIDI.md). For analysis, start the server with an explicit root containing your audio files:

```sh
ardour-ultra-mcp serve --media-root /absolute/project --export-root /absolute/project/exports
```

The installer also needs the same `--export-root` before export is allowed. Parent directory must already exist; each export uses a new child directory. Windows/PowerShell paths work as separately quoted CLI arguments, e.g. `--media-root "C:\Music Projects\Reel"`. See compatibility for unverified DAW platforms.

Explore without Ardour using `ardour-ultra-mcp serve --backend fake`. Its output is labelled simulated and it cannot render audio or execute plugins.
