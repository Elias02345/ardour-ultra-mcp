from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from . import __version__
from .backends.base import Backend
from .backends.composite import CompositeBackend
from .backends.fake import FakeBackend
from .backends.mailbox import MailboxBackend
from .backends.osc import OSCBackend
from .cli_output import diagnostics, error_lines, installation, uninstallation
from .installers.install import install, uninstall
from .installers.platforms import detect_versions, mailbox_directory
from .logging import configure_logging
from .models.base import DomainError, Options, Result
from .security.paths import PathPolicy
from .server import create_server
from .services.control import ControlService


class UnavailableBackend:
    name = "lua"

    def __init__(self, error: DomainError) -> None:
        self.error = error

    async def execute(
        self, command: str, arguments: dict[str, JsonValue], options: Options
    ) -> Result:
        raise self.error

    async def capabilities(self) -> dict[str, JsonValue]:
        raise self.error

    async def close(self) -> None:
        pass


def make_service(args: argparse.Namespace) -> ControlService:
    backend: Backend
    if args.backend == "fake":
        backend = FakeBackend()
    elif args.backend == "osc":
        backend = OSCBackend(args.osc_host, args.osc_port)
    else:
        try:
            backend = MailboxBackend(args.mailbox, args.timeout)
        except DomainError as exc:
            backend = UnavailableBackend(exc)
        if args.backend == "composite":
            backend = CompositeBackend(backend, OSCBackend(args.osc_host, args.osc_port))
    return ControlService(backend, PathPolicy(tuple(args.media_root), tuple(args.export_root)))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ardour-ultra-mcp",
        description="Local Ardour control for MCP clients. Start with: ardour-ultra-mcp install",
        epilog="Setup guide: https://github.com/Elias02345/ardour-ultra-mcp/blob/main/docs/INSTALLATION.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"ardour-ultra-mcp {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--backend",
        choices=["lua", "osc", "composite", "fake"],
        default="lua",
        help="lua (default); fake is a simulator; OSC is experimental",
    )
    common.add_argument(
        "--mailbox",
        type=Path,
        default=mailbox_directory(),
        help="private bridge directory; use the same path for install and serve",
    )
    common.add_argument(
        "--media-root",
        type=Path,
        action="append",
        default=[],
        help="allow audio analysis under this absolute directory (repeatable)",
    )
    common.add_argument(
        "--export-root",
        type=Path,
        action="append",
        default=[],
        help="allow new export directories here; set on install and serve (repeatable)",
    )
    common.add_argument("--osc-host", default="127.0.0.1")
    common.add_argument("--osc-port", type=int, default=3819)
    common.add_argument(
        "--timeout", type=float, default=15, help="bridge timeout in seconds (default: 15)"
    )
    common.add_argument("--debug", action="store_true", help="send diagnostic logs to stderr")
    common.add_argument(
        "--json",
        action="store_true",
        help="machine-readable diagnostics; configure always prints a client snippet",
    )
    sub = p.add_subparsers(dest="command", required=True)
    for name, help_text in {
        "serve": "start the MCP STDIO server (normally launched by your MCP client)",
        "doctor": "check the installation, dependencies and Ardour connection",
        "status": "show the currently connected session",
        "capabilities": "show the running backend's available operations",
        "test-connection": "check whether the Ardour bridge responds",
    }.items():
        sub.add_parser(name, parents=[common], help=help_text, description=help_text)
    installer = sub.add_parser(
        "install", parents=[common], help="install the Lua bridge and print activation steps"
    )
    installer.add_argument(
        "--ardour-config", type=Path, help="override the Ardour configuration directory"
    )
    installer.add_argument(
        "--ardour-major",
        type=int,
        choices=range(8, 20),
        default=None,
        help="Ardour major version, e.g. 9; otherwise detect or fall back to 9",
    )
    sub.add_parser(
        "uninstall", parents=[common], help="remove the unmodified bridge script, keeping backups"
    )
    configure = sub.add_parser(
        "configure",
        parents=[common],
        help="print configuration for your MCP client without changing files",
    )
    configure.add_argument("client", choices=["claude", "claude-code", "codex", "generic"])
    return p


def client_configuration(args: argparse.Namespace) -> str:
    executable = shutil.which("ardour-ultra-mcp")
    command = executable or sys.executable
    arguments = ([] if executable else ["-m", "ardour_ultra_mcp"]) + [
        "serve",
        "--backend",
        args.backend,
        "--mailbox",
        str(args.mailbox),
    ]
    for key in ["media_root", "export_root"]:
        for root in getattr(args, key):
            arguments += ["--" + key.replace("_", "-"), str(root)]
    if args.client == "codex":
        return (
            "[mcp_servers.ardour_ultra]\ncommand = "
            + json.dumps(command)
            + "\nargs = "
            + json.dumps(arguments)
            + "\n"
        )
    if args.client == "claude-code":
        # JSON avoids shell-specific quoting/escaping, including Windows/PowerShell.
        return json.dumps(
            {
                "mcpServers": {
                    "ardour-ultra": {"type": "stdio", "command": command, "args": arguments}
                }
            },
            indent=2,
        )
    return json.dumps(
        {"mcpServers": {"ardour-ultra": {"command": command, "args": arguments}}}, indent=2
    )


async def diagnose(args: argparse.Namespace) -> Result:
    service = make_service(args)
    try:
        return await service.call(
            {
                "doctor": "doctor",
                "status": "get_session_info",
                "capabilities": "get_capabilities",
                "test-connection": "ping",
            }[args.command],
            {},
        )
    finally:
        await service.backend.close()


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    configure_logging(args.debug)
    if args.timeout <= 0 or args.timeout > 3600:
        parser().error("--timeout must be >0 and <=3600 seconds")
    try:
        if args.command == "serve":
            create_server(make_service(args)).run(transport="stdio")
            return 0
        if args.command == "configure":
            print(client_configuration(args))
            return 0
        if args.command == "install":
            versions = detect_versions()
            detected = [v["major"] for v in versions if isinstance(v["major"], int)]
            major = args.ardour_major or (max(detected) if detected else 9)
            value: Any = install(args.mailbox, args.ardour_config, major, tuple(args.export_root))
            value["ardour_versions"] = versions
            value["selected_major"] = major
            value["version_selection"] = (
                "explicit"
                if args.ardour_major
                else "detected"
                if detected
                else "fallback_9_unverified"
            )
            print(json.dumps(value, indent=2) if args.json else installation(value))
            return 0
        if args.command == "uninstall":
            value = uninstall(args.mailbox)
            print(json.dumps(value, indent=2) if args.json else uninstallation(value))
            return 0
        result = asyncio.run(diagnose(args))
        print(
            result.model_dump_json(indent=2)
            if args.json
            else diagnostics(args.command, result.model_dump(mode="json"), args.backend)
        )
        if args.command == "doctor":
            connectivity = result.data.get("connectivity")
            if isinstance(connectivity, dict) and not connectivity.get("success"):
                return 2
        return 0 if result.success else 2
    except DomainError as exc:
        detail = exc.detail.model_dump(mode="json")
        print(
            json.dumps({"success": False, "error": detail}, indent=2)
            if args.json
            else "\n".join(error_lines(detail))
        )
        return 2
    except OSError as exc:
        detail = {
            "code": "PERMISSION_DENIED",
            "message": "Local filesystem operation failed.",
            "action": "Check paths and permissions.",
            "type": type(exc).__name__,
        }
        print(
            json.dumps({"success": False, "error": detail})
            if args.json
            else "\n".join(error_lines(detail))
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
