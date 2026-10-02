# Troubleshooting

Start with `doctor --json` and `test-connection --json`; diagnostics are structured. A running MCP server does not mean the bridge/session is connected.

BRIDGE_NOT_RUNNING: open a session, add the Action Hook, verify mailbox path, disable scripting sandbox only for reviewed trusted hooks. Remove/re-add after updating bridge code because Ardour restores saved factory bytecode. A blocked UI/export/modal dialog can stop timers and make heartbeat stale. Do not send replacement edits until state is known.

OUTCOME_UNCERTAIN or IPC_TIMEOUT: published requests can still execute after timeout. Never automatically repeat a mutation. Inspect actual objects in Ardour, then review request.json/processing.json/response.json. Stop/remove the hook before manually reconciling abandoned mailbox files. Back them up for diagnosis without sharing the nonce. Re-add the hook and refresh state. No automatic recovery command currently guesses whether execution occurred.

CONFLICT: observed revision changed; refresh the actual target. STALE_OBJECT: relist MIDI notes and use fresh references. OBJECT_NOT_FOUND: verify the stable ID belongs to the active playlist/current session. Do not substitute the same track number or similarly named object.

BACKEND_UNSUPPORTED/OPERATION_NOT_SUPPORTED: consult capabilities and COMPATIBILITY.md. Ardour 8.12 lacks the MIDI-region creation binding used in 9.8. Other build-specific bindings/plugin formats may be unavailable. Fake plugins do not exist in Ardour.

PERMISSION_DENIED: provide explicit absolute media/export roots, check private mailbox ownership/mode, and avoid symlink escape. FILE_EXISTS: choose a new export directory/snapshot name. Installer does not overwrite modified/unowned/symlink files silently.

Plugin parameter errors: select the exact inventory ID/format and instance ID, inspect the descriptor, use parameter_index and plugin_native units. Value display/name is not proof of Hz/dB. Preset labels are exact, not arbitrary files.

Export: master output channels and an appropriate existing Ardour export preset must be configured. Generic format editing and stems are absent. Export timeout is longer; a stalled GUI still requires investigation. An empty successful backend output is treated as failure.

OSC_TIMEOUT: verify native OSC enabled and configured port, firewall, local reply-port behavior. Sending an OSC packet alone does not prove Ardour is running or that a mutation occurred. Prefer Lua for stable-ID editing and authoritative transport readback. The native 9.8 Dummy fixture returned OSC state inconsistent with Lua after locate; a reply_received flag only proves receipt.

STDIO: send logs to stderr; do not launch through scripts that print banners to stdout. Configure an absolute command path when desktop clients cannot see your uv/pipx PATH. Use `configure` snippets to avoid shell quoting problems on Windows.
