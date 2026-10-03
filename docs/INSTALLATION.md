# Installation

[Deutsch](INSTALLATION.de.md) · [MCP clients](MCP_CLIENTS.md) · [Troubleshooting](TROUBLESHOOTING.md) · [Documentation](README.md)

Follow the numbered steps in order. Commands go in a terminal, not in Ardour's scripting console. Use PowerShell on Windows. Your MCP client will launch the server after setup.

## Before you start

- Install and launch Ardour once so its configuration directory exists. Linux Ardour **9.8** is the most thoroughly tested native version; **8.12** has a smaller verified API set.
- Choose an MCP client that supports local STDIO servers. No account/API key is needed by this server; a client/model may have its own requirements.
- Have internet access for installation. Runtime control and audio analysis are local.
- Use a disposable Ardour session for the first connection and editing tests.

The Python layer is tested on Linux, macOS and Windows with Python 3.11–3.14. **Native macOS/Windows Ardour integration remains unverified**. In particular, native Windows Lua heartbeat replacement and DACL checks need further work. This guide describes installation paths, not certification of those DAW platforms. See [compatibility](COMPATIBILITY.md).

## 1. Install uv

Skip this step if `uv --version` already works. uv creates an isolated tool environment and can download a suitable Python, so you do not need to manage Python yourself.

**Linux / macOS** — the [official uv installer](https://docs.astral.sh/uv/getting-started/installation/):

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows PowerShell** — use Windows Package Manager:

```powershell
winget install --id=astral-sh.uv -e
```

If `winget` is unavailable, use the alternatives in the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/). Review installer scripts before running them if you use that route.

Close and reopen the terminal, then check:

```sh
uv --version
```

## 2. Install Ardour Ultra MCP

Run this from **any directory**. It installs the current GitHub `main` archive with the optional analysis dependencies; Git is not required. The package is **not published to PyPI**.

```sh
uv tool install --python 3.12 "ardour-ultra-mcp[analysis] @ https://github.com/Elias02345/ardour-ultra-mcp/archive/refs/heads/main.zip"
uv tool update-shell
```

Open a new terminal and check:

```sh
ardour-ultra-mcp --version
```

Expected: `ardour-ultra-mcp 0.1.0`. If the command is missing, see [PATH troubleshooting](TROUBLESHOOTING.md#command-not-found).

The direct archive installation was tested on Linux. The Windows/macOS bootstrap commands are from uv's official documentation; native installs on those operating systems were not run here. `main` is a moving development branch. To pin an exact revision, replace `refs/heads/main.zip` with a reviewed commit SHA followed by `.zip`.

## 3. Install and activate the bridge

```sh
ardour-ultra-mcp install
```

This installs the allowlisted Lua script, creates a private IPC directory and backs up files it replaces. It prints the chosen Ardour version and paths. Version detection failure is visible; the fallback is **Ardour 9**. For another version or a custom build:

```sh
ardour-ultra-mcp install --ardour-major 8
# Custom configuration directory, if required:
ardour-ultra-mcp install --ardour-config "/absolute/path/to/Ardour9"
```

Then use Ardour itself:

1. Restart Ardour if it was open during installation. Open a disposable session.
2. In Ardour 9.8, open **Edit → Lua Scripts → Script Manager**.
3. Select **Action Hooks**, click **New Hook**, then select **Ardour Ultra MCP** and confirm the dialog.
4. Leave Ardour and the session open.

English UI labels are verified against the 9.8 source. The official manual/older UI may call the menu **Scripted Actions → Manage**. Translated labels vary. The hook must be an **Action Hook**, which runs in the GUI context.

The hook needs Lua file I/O. Ardour 9.8's `sandbox-all-lua-scripts` defaults to `false`; a visible Preferences switch was not verified. Usually no preference change is needed. If sandboxing was explicitly enabled in your configuration, follow [the specific troubleshooting steps](TROUBLESHOOTING.md#lua-file-io-is-blocked). Changing that setting affects all Lua scripts; activate only reviewed, trusted scripts. The installer leaves the setting untouched.

## 4. Verify the connection

```sh
ardour-ultra-mcp test-connection
ardour-ultra-mcp doctor
```

The first command should report **Connection OK: the Ardour Lua bridge responds.** Doctor checks package/SDK versions, analysis dependencies and bridge connectivity. Both should exit with code `0`; code `2` means a setup or connection problem. Fix that before editing. A stopped audio engine can still permit a bridge connection; enable/configure Ardour's audio engine before playback or rendering.

For machine-readable diagnostics, append `--json`. Keep diagnostics private if they contain project paths.

## 5. Connect one MCP client

Choose [Claude Desktop, Claude Code, Codex or a generic STDIO client](MCP_CLIENTS.md). Use the generated configuration so desktop applications can find the executable. After the client connects, start with the read-only prompt in [quick start](QUICK_START.md).

Setup is complete when the bridge responds, doctor succeeds and your client discovers the tools/resources.

## Optional: allow audio analysis and exports

This is not needed for the initial connection. Create a dedicated project/export parent directory first. Only explicitly permitted absolute paths are accessible.

```sh
ardour-ultra-mcp install --export-root "/absolute/project/exports"
ardour-ultra-mcp configure claude --media-root "/absolute/project" --export-root "/absolute/project/exports"
```

Use the name of your client instead of `claude`. Remove and re-add the Ardour hook after reinstalling, then merge the new client snippet and restart the client. The installer and server need matching export roots. Each render creates a **new child directory**; existing destinations are refused. Export is experimental and uses a configured Ardour export preset. See [audio analysis](AUDIO_ANALYSIS.md).

On Windows, use quoted native paths, for example `--media-root "C:\Music Projects\Reel"`. If using `--mailbox`, repeat the **same directory** for install, test-connection, doctor and configure.

## Update

1. Save your session and close your MCP client.
2. In Ardour's Script Manager, remove the **Ardour Ultra MCP** hook, then close Ardour.
3. Reinstall the latest archive:

```sh
uv tool install --reinstall --python 3.12 "ardour-ultra-mcp[analysis] @ https://github.com/Elias02345/ardour-ultra-mcp/archive/refs/heads/main.zip"
ardour-ultra-mcp install
```

4. Repeat any original `--ardour-major`, `--ardour-config`, `--mailbox` and `--export-root` options. Reinstalling without export roots resets the bridge's export permissions.
5. Reopen Ardour, add the hook again, rerun the connection checks, then restart the MCP client.

Re-adding the hook is necessary: Ardour persists compiled callbacks and does not reload them merely because the script file changed. Keep installer backups until you have verified the update.

## Uninstall

1. Save your session and remove the hook in Ardour's Script Manager.
2. Close your MCP client and run:

```sh
ardour-ultra-mcp uninstall
uv tool uninstall ardour-ultra-mcp
```

3. Remove just this server's entry from your MCP client configuration.

Uninstall retains the mailbox and backups for review and refuses to delete a modified script. Use the original `--mailbox` option if customized. It does not delete your sessions or audio.

## Alternative: install from a checkout

For contributors or users who already have Git and Python 3.11+:

```sh
git clone https://github.com/Elias02345/ardour-ultra-mcp.git
cd ardour-ultra-mcp
uv tool install --python 3.12 ".[analysis]"
# Or, if pipx is already installed with Python 3.11+:
# pipx install ".[analysis]"
```

Then continue at step 3. For an editable development environment, use [development instructions](DEVELOPMENT.md). To omit analysis, remove `[analysis]` from the installation requirement.

## Default locations

These directories are discovered automatically; most users never need to edit them.

| OS | Ardour 9 configuration | Private bridge mailbox |
|---|---|---|
| Linux | `$XDG_CONFIG_HOME/ardour9` or `~/.config/ardour9` | `$XDG_STATE_HOME/ardour-ultra-mcp` or `~/.local/state/ardour-ultra-mcp` |
| macOS | `~/Library/Preferences/Ardour9` | `~/Library/Application Support/ardour-ultra-mcp` |
| Windows | `$XDG_CONFIG_HOME/Ardour9` or `%LOCALAPPDATA%\Ardour9` | `%LOCALAPPDATA%\ardour-ultra-mcp` |

Use `install --ardour-config` for vendor builds. Installation does not install Ardour, open/replace sessions, alter audio configuration, enable OSC or modify MCP client files.
