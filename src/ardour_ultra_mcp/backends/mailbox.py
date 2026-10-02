"""Serialized, bounded, correlated local IPC. Published mutations are never retried."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import JsonValue, ValidationError

from ..models.base import DomainError, ErrorCode, Options, Result
from ..security.paths import private_directory
from ..services.catalog import CATALOG, UNSUPPORTED

MAX_BYTES = 4 * 1024 * 1024


def read_bounded(path: Path, limit: int = MAX_BYTES) -> bytes:
    if path.is_symlink():
        raise DomainError(ErrorCode.PERMISSION_DENIED, "IPC file must not be a symlink.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise DomainError(ErrorCode.PROTOCOL_ERROR, "IPC message exceeds size limit.")
    return data


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    data = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()
    if len(data) > MAX_BYTES:
        raise DomainError(ErrorCode.VALIDATION_ERROR, "IPC request exceeds 4 MiB.")
    part = path.with_name(path.name + "." + secrets.token_hex(8) + ".part")
    try:
        fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


@contextmanager
def slot_lock(path: Path) -> Iterator[None]:
    if path.is_symlink():
        raise DomainError(ErrorCode.PERMISSION_DENIED, "Lock must not be a symlink.")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            if os.name == "nt":
                msvcrt: Any = importlib.import_module("msvcrt")

                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DomainError(
                ErrorCode.BUSY,
                "Another MCP client owns the mailbox.",
                "Wait for the active request to finish.",
            ) from exc
        try:
            yield
        finally:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class MailboxBackend:
    name = "lua"

    def __init__(self, directory: Path, timeout: float = 15.0) -> None:
        self.directory = private_directory(directory)
        self.timeout = timeout
        self._lock = asyncio.Lock()
        try:
            config = json.loads(read_bounded(self.directory / "bridge-config.json", 16384))
            self.token: str = config["token"]
            if len(self.token) != 64 or config["protocol"] != 1:
                raise ValueError("invalid config")
        except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
            raise DomainError(
                ErrorCode.BRIDGE_NOT_RUNNING,
                "Bridge configuration missing or invalid.",
                "Run ardour-ultra-mcp install, then activate its EditorHook in Ardour.",
            ) from exc

    def heartbeat(self) -> dict[str, JsonValue]:
        try:
            value = json.loads(read_bounded(self.directory / "heartbeat.json", 32768))
            if (
                not isinstance(value, dict)
                or value.get("protocol") != 1
                or not isinstance(value.get("epoch"), str)
            ):
                raise ValueError("invalid heartbeat")
            if time.time() - float(value.get("time", 0)) > 4:
                raise ValueError("stale heartbeat")
            return value
        except (FileNotFoundError, ValueError, TypeError) as exc:
            raise DomainError(
                ErrorCode.BRIDGE_NOT_RUNNING,
                "EditorHook heartbeat is missing or stale.",
                "Open a session, activate the Ultra MCP EditorHook; check Ardour's Lua console.",
            ) from exc

    async def execute(
        self, command: str, arguments: dict[str, JsonValue], options: Options
    ) -> Result:
        if command not in CATALOG:
            raise DomainError(ErrorCode.OPERATION_NOT_SUPPORTED, "Command not allowlisted.")
        async with self._lock:
            with slot_lock(self.directory / "client.lock"):
                heart = self.heartbeat()
                if (self.directory / "request.json").exists() or (
                    self.directory / "processing.json"
                ).exists():
                    raise DomainError(
                        ErrorCode.OUTCOME_UNCERTAIN,
                        "A prior published request has not been reconciled.",
                        "Inspect/recover the mailbox; never retry a mutation without refreshing Ardour state.",
                    )
                commands = heart.get("commands")
                if not isinstance(commands, list) or command not in commands:
                    raise DomainError(
                        ErrorCode.BACKEND_UNSUPPORTED,
                        "Running bridge does not advertise this command.",
                        "Inspect get_capabilities; check Ardour bindings and reload an updated hook.",
                        command=command,
                    )
                response = self.directory / "response.json"
                response.unlink(missing_ok=True)  # late response cannot match new request ID
                request_id = secrets.token_hex(16)
                timeout = max(self.timeout, 300.0) if command == "render_range" else self.timeout
                envelope: dict[str, JsonValue] = {
                    "protocol": 1,
                    "id": request_id,
                    "epoch": heart["epoch"],
                    "token": self.token,
                    "expires": time.time() + timeout,
                    "command": command,
                    "arguments": arguments,
                    "options": options.model_dump(mode="json"),
                }
                atomic_json(self.directory / "request.json", envelope)
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if response.exists():
                        try:
                            value = json.loads(read_bounded(response))
                            if (
                                value.get("id") != request_id
                                or value.get("epoch") != heart["epoch"]
                                or value.get("protocol") != 1
                            ):
                                raise DomainError(
                                    ErrorCode.PROTOCOL_ERROR,
                                    "Reply correlation failed.",
                                    "Inspect mailbox and refresh state before retrying.",
                                )
                            result = Result.model_validate(value["result"])
                        except (ValueError, KeyError, TypeError, ValidationError) as exc:
                            raise DomainError(
                                ErrorCode.PROTOCOL_ERROR, "Invalid bridge response."
                            ) from exc
                        response.unlink(missing_ok=True)
                        return result
                    await asyncio.sleep(0.01)
                code = (
                    ErrorCode.OUTCOME_UNCERTAIN
                    if CATALOG[command].mutates and not options.dry_run
                    else ErrorCode.IPC_TIMEOUT
                )
                raise DomainError(
                    code,
                    "Published bridge request timed out; it may still execute.",
                    "Refresh affected state and reconcile request/processing files before issuing another mutation.",
                    request_id=request_id,
                    timeout_seconds=timeout,
                )

    async def capabilities(self) -> dict[str, JsonValue]:
        heart = self.heartbeat()
        features = heart.get("commands", [])
        return {
            "backend": self.name,
            "commands": features,
            "unsupported": UNSUPPORTED,
            "revision_scope": "observed route mixer, region and group properties; MIDI guards exact model; excludes human plugin/automation/ports/tempo edits",
            "experimental_commands": ["render_range"],
            "native_undo": ["midi_diffs", "region_diffs", "automation_points"],
            "heartbeat": heart,
        }

    async def close(self) -> None:
        pass
