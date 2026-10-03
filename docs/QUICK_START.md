# First successful session

[Install first](INSTALLATION.md) · [Deutsch](INSTALLATION.de.md) · [Connect your client](MCP_CLIENTS.md)

This walkthrough starts after installation. Keep Ardour open with a disposable session and the **Ardour Ultra MCP** Action Hook active.

## Check readiness

```sh
ardour-ultra-mcp test-connection
ardour-ultra-mcp doctor
```

Both commands should succeed. `test-connection` should report **Connection OK**. If you used a custom mailbox, repeat `--mailbox` with that path for both commands.

Ask your configured MCP client:

> Inspect the Ardour connection, session and capabilities. List the tracks and unsupported features. Make no changes.

Expected: the agent uses inspection tools and returns the session name, tracks and capability limitations. A simulator result must be labelled **simulated**.

## Try a controlled edit

In the disposable session, ask:

> Check whether MIDI track creation is available. Preflight creating a stereo MIDI track named Bass. If valid, create it, retain its stable ID, set its gain to −4.25 dB and its signed normalized pan to −0.35, then read the track back. Report the changes and any errors.

The agent should use `create_track` with `dry_run: true`, then the real call. `set_track_gain` uses `gain_db`; `set_track_pan` uses `pan`. Pan is signed normalized azimuth, not an angle. The returned `data.id` is used as `track_id`; a track number/name is not a substitute.

All tool arguments are wrapped in `request`. For example, the **MCP input**, not a shell command, for the preflight is:

```json
{"request": {"name": "Bass", "kind": "midi", "channels": 2, "dry_run": true}}
```

Do not claim an instrument is loaded merely because a MIDI track exists. Inspect available instruments and plugins before adding one. Follow [MIDI](MIDI.md), [plugins](PLUGINS.md), [automation](AUTOMATION.md) and [routing](ROUTING.md) for precise schemas and limitations.

## Render and analyze later

Permit the project/export paths using the [optional installation step](INSTALLATION.md#optional-allow-audio-analysis-and-exports). Ardour needs a working audio engine, master outputs and a suitable export preset. Master export is experimental; stems and arbitrary export-format setters are unavailable. See [audio analysis](AUDIO_ANALYSIS.md).

## Explore without Ardour

Configure your client with `ardour-ultra-mcp configure generic --backend fake` (or your client name). This launches the deterministic test backend. It can exercise tool calls but cannot execute real plugins or render audio. Its state resets when the server process exits.
