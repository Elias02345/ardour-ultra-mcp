"""Readable onboarding output; MCP STDIO and --json never pass through this module."""

from __future__ import annotations

from typing import Any


def error_lines(error: dict[str, Any]) -> list[str]:
    lines = [f"ERROR [{error['code']}]: {error['message']}", f"Next: {error['action']}"]
    if error["code"] == "BRIDGE_NOT_RUNNING":
        lines.append(
            "Run ardour-ultra-mcp install, then open a session and add the Action Hook "
            "in Edit > Lua Scripts > Script Manager > Action Hooks > New Hook."
        )
    return lines


def installation(value: dict[str, Any]) -> str:
    lines = [
        f"Bridge script installed for Ardour {value['selected_major']}.",
        f"Script:  {value['script']}",
        f"Mailbox: {value['mailbox']}",
    ]
    if value["version_selection"] == "fallback_9_unverified":
        lines += [
            "Ardour version could not be detected; the installer selected Ardour 9.",
            "If you use another version, rerun install with --ardour-major VERSION.",
        ]
    lines += [f"Backup: {path}" for path in value["backups"]]
    lines += [
        "",
        "Next steps (the bridge is not active yet):",
        "1. Restart Ardour if it was open, then open a disposable session.",
        "2. Edit > Lua Scripts > Script Manager > Action Hooks > New Hook.",
        "   Select Ardour Ultra MCP. For updates, remove the old hook first.",
        "3. Run ardour-ultra-mcp test-connection, then ardour-ultra-mcp doctor.",
        "   Use the same --mailbox option if you customized the mailbox path.",
        "4. Run ardour-ultra-mcp configure CLIENT and follow docs/INSTALLATION.md.",
        "",
        "The reviewed hook needs Lua file I/O. Ardour 9.8 allows this by default.",
        "If Lua sandboxing was enabled, see docs/TROUBLESHOOTING.md before changing it.",
        "Setup guide: https://github.com/Elias02345/ardour-ultra-mcp/blob/main/docs/INSTALLATION.md",
    ]
    return "\n".join(lines)


def uninstallation(value: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Bridge script removed: {value['removed_script']}",
            f"Mailbox and backups retained: {value['mailbox_retained']}",
            value["required_ui_step"],
            "Remove the server entry from your MCP client. To remove the Python tool:",
            "uv tool uninstall ardour-ultra-mcp",
        ]
    )


def diagnostics(command: str, value: dict[str, Any], backend: str) -> str:
    if not value["success"]:
        return "\n".join(error_lines(value["error"]))
    data = value["data"]
    lines: list[str] = []
    if command == "doctor":
        lines = [
            f"Ardour Ultra MCP {data['package']} | Python {data['python']} | {data['platform']}",
            f"MCP SDK: {data['mcp_sdk']}",
            f"Backend: {backend}",
            "Ardour detected: "
            + (
                ", ".join(data["ardour_candidates"])
                or "no executable found; use --ardour-major when installing"
            ),
        ]
        missing = [name for name, present in data["analysis_dependencies"].items() if not present]
        lines.append(
            "Audio analysis: "
            + ("missing " + ", ".join(missing) if missing else "dependencies installed")
        )
        connection = data["connectivity"]
        if not connection["success"]:
            lines += ["Connection: not ready", *error_lines(connection["error"])]
        else:
            lines += connection_lines(connection["data"], backend)
        lines.append("Native platform verification: see docs/COMPATIBILITY.md.")
    elif command == "test-connection":
        lines = connection_lines(data, backend)
        lines.append(
            "Next: ardour-ultra-mcp configure CLIENT (claude, claude-code, codex or generic)."
        )
    elif command == "status":
        lines = [
            "Session: " + str(data.get("name", "unnamed")),
            "ID: " + str(data.get("session_id", "unavailable")),
            "Sample rate: " + str(data.get("sample_rate", "unavailable")) + " Hz",
        ]
        if data.get("simulated"):
            lines.append("SIMULATED: this is not a connection to Ardour.")
    else:
        commands = data.get("commands", [])
        lines = [
            f"Backend: {data.get('backend', backend)}",
            f"Registered MCP tools: {data['tool_count']}",
            f"Backend commands available now: {len(commands)}",
            "Available: " + ", ".join(commands),
            "Use --json for the complete capability manifest, including unsupported features.",
        ]
        if data.get("simulated"):
            lines.append("SIMULATED: capabilities describe the test backend, not Ardour.")
    lines += [f"Warning: {warning}" for warning in value.get("warnings", [])]
    return "\n".join(lines)


def connection_lines(data: dict[str, Any], backend: str) -> list[str]:
    if data.get("simulated"):
        return ["SIMULATED: the fake backend responds. Ardour was not contacted."]
    if backend == "osc":
        return [
            "OSC query answered. Native editing/readback limitations: see docs/COMPATIBILITY.md."
        ]
    lines = ["Connection OK: the Ardour Lua bridge responds."]
    if "session_open" in data:
        lines.append("Session: " + ("open" if data["session_open"] else "not open"))
    if "engine_running" in data:
        lines.append("Audio engine: " + ("running" if data["engine_running"] else "stopped"))
    return lines
