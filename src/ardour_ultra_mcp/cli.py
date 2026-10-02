from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from .backends.base import Backend
from .backends.composite import CompositeBackend
from .backends.fake import FakeBackend
from .backends.mailbox import MailboxBackend
from .backends.osc import OSCBackend
from .installers.install import install, uninstall
from .installers.platforms import mailbox_directory
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
        prog="ardour-ultra-mcp", description="Local typed Ardour MCP; real Lua bridge by default"
    )
    p.add_argument("--version", action="version", version="ardour-ultra-mcp 0.1.0")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--backend", choices=["lua", "osc", "composite", "fake"], default="lua")
    common.add_argument("--mailbox", type=Path, default=mailbox_directory())
    common.add_argument("--media-root", type=Path, action="append", default=[])
    common.add_argument("--export-root", type=Path, action="append", default=[])
    common.add_argument("--osc-host", default="127.0.0.1")
    common.add_argument("--osc-port", type=int, default=3819)
    common.add_argument("--timeout", type=float, default=15)
    common.add_argument("--debug", action="store_true")
    common.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ["serve", "doctor", "status", "capabilities", "test-connection"]:
        sub.add_parser(name, parents=[common])
    installer = sub.add_parser("install", parents=[common])
    installer.add_argument("--ardour-config", type=Path)
    installer.add_argument("--ardour-major", type=int, choices=range(8, 20), default=9)
    sub.add_parser("uninstall", parents=[common])
    configure = sub.add_parser("configure", parents=[common])
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
            {"ardour-ultra": {"type": "stdio", "command": command, "args": arguments}}, indent=2
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
            value: Any = install(
                args.mailbox, args.ardour_config, args.ardour_major, tuple(args.export_root)
            )
            print(json.dumps(value, indent=2))
            return 0
        if args.command == "uninstall":
            print(json.dumps(uninstall(args.mailbox), indent=2))
            return 0
        result = asyncio.run(diagnose(args))
        print(result.model_dump_json(indent=2))
        if args.command == "doctor":
            connectivity = result.data.get("connectivity")
            if isinstance(connectivity, dict) and not connectivity.get("success"):
                return 2
        return 0 if result.success else 2
    except DomainError as exc:
        print(json.dumps({"success": False, "error": exc.detail.model_dump(mode="json")}, indent=2))
        return 2
    except OSError as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": "Local filesystem operation failed.",
                        "action": "Check paths and permissions.",
                        "type": type(exc).__name__,
                    },
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
