# Troubleshooting

[Installation](INSTALLATION.md) · [Deutsch](INSTALLATION.de.md) · [MCP clients](MCP_CLIENTS.md)

Start with `ardour-ultra-mcp doctor` and `ardour-ultra-mcp test-connection`. Append `--json` for structured output. If you customized the mailbox, repeat `--mailbox` with the installed path. A running MCP server does not prove Ardour is connected.

## Command not found

1. Run `uv tool list` to check that the package is installed.
2. Run `uv tool update-shell`, then close and reopen your terminal.
3. Run `uv tool dir --bin` to find the executable directory and check your PATH.

A desktop client may have a different PATH from your terminal. Use `ardour-ultra-mcp configure CLIENT`: it prints an absolute executable path. Do not put terminal banners/wrappers in front of an MCP STDIO server.

## BRIDGE_NOT_RUNNING

Open an Ardour session and add **Ardour Ultra MCP** under **Edit → Lua Scripts → Script Manager → Action Hooks → New Hook** (9.8 English labels). Restart Ardour if the script is missing. Check the script/config paths printed by `install` and that every command uses the same mailbox.

After updates or export-permission changes, remove and re-add the hook; Ardour restores saved factory bytecode. A modal dialog, blocked UI or ongoing export may pause timers and make the heartbeat stale. Resolve that first.

Native Windows heartbeat replacement remains unverified: Python CI passing is not proof that the installed Ardour Lua runtime can replace the heartbeat file. See [compatibility](COMPATIBILITY.md).

## Lua file I/O is blocked

The bridge needs `io` and `os` file operations outside Ardour's realtime thread. Ardour 9.8 defines `sandbox-all-lua-scripts` with default **false** in `gtk2_ardour/ui_config_vars.inc.h`. No visible Preferences control was found in that version; the earlier instruction to use “Preferences → Scripting” was incorrect.

If your configuration explicitly enables sandboxing:

1. Review the installed bridge and any other active Lua scripts. Changing this setting affects **all** Lua scripts.
2. Close Ardour completely and back up the `ui_config` file in the Ardour configuration directory printed during installation.
3. In that XML file's `UI` section, change an existing `<Option name="sandbox-all-lua-scripts" value="1"/>` (or true) to `value="0"`. Do not replace the whole file or create duplicate options. If the option is absent, the 9.8 default is already false; investigate other causes instead.
4. Restart Ardour, re-add the hook and rerun the connection test.

Vendor builds may differ. This conditional manual config remedy is source-backed, not a tested GUI preference workflow. The installer does not change sandbox settings.

## IPC_TIMEOUT or OUTCOME_UNCERTAIN

A published request can execute after timeout. **Do not blindly repeat a mutation.** Inspect actual objects in Ardour first. Stop/remove the hook before reconciling abandoned `request.json`, `processing.json` or `response.json` files. Back up files for diagnosis without sharing the private nonce. Re-add the hook and refresh state after reconciling the outcome. No automatic recovery command guesses whether a change occurred.

## CONFLICT, STALE_OBJECT or OBJECT_NOT_FOUND

| Error | Next step |
|---|---|
| `CONFLICT` | Refresh state and inspect the target's current revision. |
| `STALE_OBJECT` | Relist MIDI notes and use fresh guarded references. |
| `OBJECT_NOT_FOUND` | Check that the stable ID belongs to the active session/playlist. |

Do not substitute a track number or similarly named object for a stale ID.

## Unsupported operations or plugin errors

Consult `ardour-ultra-mcp capabilities --json` and [compatibility](COMPATIBILITY.md). Ardour 8.12 lacks the MIDI-region creation binding used in 9.8. Other bindings/formats depend on the build. Simulator plugins are not actual installed Ardour plugins.

Use an exact plugin inventory ID/format and instance ID. Inspect its parameter descriptor, select `parameter_index` and use `plugin_native` units. A display/name is not proof of Hz or dB. Preset labels must match Ardour's available presets.

## PERMISSION_DENIED or FILE_EXISTS

Use explicit absolute media/export roots and check mailbox ownership/permissions. Symlink escapes are refused. Choose a **new** export directory or snapshot name; existing targets are not overwritten. Uninstall refuses modified scripts. See [security](SECURITY.md).

## Export fails

Configure Ardour's audio engine, master output channels and an appropriate existing export preset. Generic format editing and stems are not implemented. Export can take longer and block UI timers; investigate a stalled GUI before issuing another change. An empty backend output is treated as failure.

## OSC_TIMEOUT

OSC is optional; the default Lua backend does not require enabling it. For deliberate OSC use, check Ardour's OSC setting, port, firewall and local reply behavior. Sending a packet alone does not prove a mutation occurred. Native 9.8 Dummy tests showed inconsistent OSC versus Lua transport readback after locate. Prefer Lua for authoritative state and stable-ID editing.

## Report a reproducible problem

Include your OS, Ardour version, installation method, command, error code and sanitized `doctor --json` output. Do not publish mailbox nonces, private session contents or audio. Native integration evidence and reproducible tests are in [testing](TESTING.md).
