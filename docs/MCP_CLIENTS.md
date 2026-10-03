# Connect an MCP client

[Install the bridge first](INSTALLATION.md) · [Deutsch](INSTALLATION.de.md) · [Troubleshooting](TROUBLESHOOTING.md)

Prerequisite: `ardour-ultra-mcp test-connection` and `ardour-ultra-mcp doctor` succeed with Ardour and a session open. Choose **one** client below. The client starts `serve` automatically; running it in a separate terminal is usually unnecessary.

`configure` **prints** configuration. It does not change a file. Use the generated absolute executable path and preserve all existing server entries. Back up a config file before merging; paste only the new server entry inside the existing object/table.

## Claude Desktop

Run:

```sh
ardour-ultra-mcp configure claude
```

It prints a JSON `mcpServers` object with an `ardour-ultra` entry.

1. Open Claude Desktop's **Settings → Developer → Edit Config**.
2. Back up the configuration file. If it is empty, paste the full generated JSON. Otherwise merge only `ardour-ultra` into the existing `mcpServers` object; JSON cannot contain duplicate top-level keys or comments.
3. Save and restart Claude Desktop completely.
4. Check that the server/tools appear. Keep Ardour and its session open.

Typical config file locations:

| OS | File |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Linux Desktop availability is not assumed. See the [official local MCP guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers).

## Claude Code

For the default installation, run:

```sh
claude mcp add --transport stdio --scope user ardour-ultra -- ardour-ultra-mcp serve
claude mcp list
```

Restart an existing Claude Code session after adding the server. If the client cannot find the executable, or you use custom mailbox/media/export paths, use:

```sh
ardour-ultra-mcp configure claude-code
```

Merge the generated entry into your project's `.mcp.json`. It includes `type: stdio` and the absolute command path. Review project MCP trust prompts before enabling it. Choose the CLI/user-scope method **or** the project-config method to avoid duplicate registrations.

See the [official Claude Code MCP guide](https://code.claude.com/docs/en/mcp).

## Codex

For the default installation:

```sh
codex mcp add ardour-ultra -- ardour-ultra-mcp serve
codex mcp list
```

For an absolute command path and any custom paths:

```sh
ardour-ultra-mcp configure codex
```

Back up `~/.codex/config.toml`, then append or replace just the generated `[mcp_servers.ardour_ultra]` table. Do not define the same table twice. Restart the Codex session.

See the [official Codex MCP guide](https://developers.openai.com/codex/mcp/). The CLI method uses the name `ardour-ultra`; the generated TOML uses `ardour_ultra`. Choose one method so the server is not registered twice.

## Generic STDIO clients

```sh
ardour-ultra-mcp configure generic
```

For clients using the `mcpServers` JSON format, merge the generated entry. For other formats, copy its `command` and `args` values into the client's STDIO configuration. The executable is launched locally with `serve` and communicates over stdin/stdout; no HTTP URL or port is required.

The official Python SDK Client was tested in current/auto and legacy modes. Claude Desktop, Claude Code and Codex applications were not launched in the test environment. Formats/commands follow their official documentation; this is not a claim of branded-client E2E verification.

## Custom paths and analysis permissions

Generate the configuration with the **same mailbox** as the installer and explicit media/export roots if needed:

```sh
ardour-ultra-mcp configure codex --mailbox "/absolute/private/mailbox" --media-root "/absolute/project" --export-root "/absolute/project/exports"
```

The bridge must also be installed with matching `--export-root` permissions before exporting. Quote paths with spaces as separate arguments. On PowerShell, native paths such as `"C:\Music Projects\Reel"` are supported by the Python layer; native Ardour Windows verification remains open.

## First request

After the client discovers Ardour Ultra MCP, ask:

> Inspect the Ardour connection, session and runtime capabilities. List the tracks and unsupported features. Make no changes.

MCP tools wrap their input in `{"request": {...}}`. For example, a read-only tool call is:

```json
{"request": {}}
```

Use it with `get_session_info` or `get_capabilities`. See the [quick start](QUICK_START.md) and [tool reference](TOOL_REFERENCE.md) before the first mutation.
