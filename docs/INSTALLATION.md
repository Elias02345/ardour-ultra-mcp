# Installation and MCP clients

Python 3.11 or newer is required. Core dependencies are the official stable MCP v2 SDK and Pydantic. Offline audio analysis is an optional extra. No API keys or accounts are needed.

From the repository directory:

```sh
uv tool install '.[analysis]'
# or
pipx install '.[analysis]'
# or an isolated development environment
python -m venv .venv
# Linux/macOS: .venv/bin/python; Windows: .venv\Scripts\python.exe
.venv/bin/python -m pip install '.[analysis]'
# Windows PowerShell: .venv\Scripts\python.exe -m pip install ".[analysis]"
```

Use the Python inside the new virtual environment for the pip command. This repository is not published to PyPI; `pipx install ardour-ultra-mcp` is a future release command, not a verified current installation.

```sh
ardour-ultra-mcp install --ardour-major 9
```

The installer discovers candidate executables, computes native configuration paths, creates a private mailbox and nonce, installs the reviewed allowlisted Lua script, and backs up existing script/config files. It leaves hook activation and scripting sandbox preferences explicit. It does not launch/replace sessions, alter audio configuration, automatically enable OSC, install Ardour, or silently modify client settings. Version probing uses the official --version flag of discovered binaries. The newest detected major selects the default configuration directory; no detected version falls back to major 9 with an explicit unverified label. Use --ardour-major/--ardour-config for side-by-side or vendor builds.

Default config locations: Linux `$XDG_CONFIG_HOME/ardour9` or `~/.config/ardour9`; macOS `~/Library/Preferences/Ardour9`; Windows `$XDG_CONFIG_HOME/Ardour9` or `%LOCALAPPDATA%/Ardour9`. Override a vendor/custom build using `--ardour-config`. Default mailbox: Linux XDG state directory, macOS Application Support, Windows LOCALAPPDATA. Runtime details are printed by install/doctor. Config discovery on macOS/Windows is source-backed, DAW validation remains external.

Activate **Ardour Ultra MCP** as an Action Hook in Ardour's Script Manager. Preferences → Scripting → Sandbox all Lua scripts must be disabled for this reviewed non-realtime hook to use file IPC. Open a session and run `test-connection`. When reinstalling changed code, remove and re-add the hook: Ardour persists compiled callbacks and does not automatically reload a changed script file.

`install --export-root /absolute/exports` stores bridge export permissions. Provide matching roots to `serve`. Uninstall backs up and removes only the unmodified installed script; it preserves mailbox/backups and asks you to remove the hook manually. It refuses to remove a script changed by the user.

## Claude Desktop

Run `ardour-ultra-mcp configure claude`; merge its `mcpServers` member into your existing JSON. Restart Desktop. Use an absolute executable path when the client has a restricted PATH.

```json
{"mcpServers":{"ardour-ultra":{"command":"ardour-ultra-mcp","args":["serve"]}}}
```

Config file: macOS `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows `%APPDATA%\Claude\claude_desktop_config.json`. Official [local server guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers) fetched 2026-10-02. Desktop itself was not launched here; Linux Desktop availability is not assumed.

## Claude Code

Current [official documentation](https://code.claude.com/docs/en/mcp) fetched 2026-10-02:

```sh
claude mcp add --transport stdio --scope user ardour-ultra -- ardour-ultra-mcp serve
```

Alternatively `configure claude-code` prints the project `.mcp.json` `mcpServers` block with `type: stdio`. Merge rather than replace an existing file. No automated client modification is implemented.

## Codex

Current [official documentation](https://developers.openai.com/codex/mcp/) fetched 2026-10-02:

```sh
codex mcp add ardour-ultra -- ardour-ultra-mcp serve
```

Or merge `configure codex` into `~/.codex/config.toml`:

```toml
[mcp_servers.ardour_ultra]
command = "ardour-ultra-mcp"
args = ["serve"]
```

For generic clients, start the executable with `serve`, communicate using MCP STDIO, and inspect tools/resources. Structured tool input wraps arguments in `request`. Compatibility was tested using the official SDK's Client; named client applications require external verification.
