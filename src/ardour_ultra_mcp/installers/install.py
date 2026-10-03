from __future__ import annotations

import hashlib
import importlib.resources
import json
import os
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..backends.mailbox import atomic_json, read_bounded
from ..models.base import DomainError, ErrorCode
from ..security.paths import private_directory
from .platforms import config_directory, find_ardour, mailbox_directory


def lua_string(value: str) -> str:
    """Encode UTF-8 bytes as fixed-width Lua decimal escapes, never interpolate executable text."""
    return '"' + "".join(f"\\{b:03d}" for b in value.encode("utf-8")) + '"'


def backup(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.is_symlink():
        raise DomainError(ErrorCode.PERMISSION_DENIED, "Refusing to replace a symlink.")
    suffix = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "." + secrets.token_hex(4)
    target = path.with_name(path.name + ".backup." + suffix)
    shutil.copy2(path, target)
    return str(target)


def install(
    directory: Path | None = None,
    ardour_config: Path | None = None,
    major: int = 9,
    export_roots: tuple[Path, ...] = (),
) -> dict[str, Any]:
    root = private_directory(directory or mailbox_directory())
    configuration = ardour_config or config_directory(major)
    scripts = configuration / "scripts"
    if scripts.is_symlink():
        raise DomainError(
            ErrorCode.PERMISSION_DENIED, "Ardour scripts directory must not be a symlink."
        )
    scripts.mkdir(parents=True, exist_ok=True)
    config_file = root / "bridge-config.json"
    previous = json.loads(read_bounded(config_file, 16384)) if config_file.exists() else None
    if previous and (
        previous.get("protocol") != 1
        or not isinstance(previous.get("token"), str)
        or len(previous["token"]) != 64
    ):
        raise DomainError(ErrorCode.PROTOCOL_ERROR, "Existing bridge config is invalid.")
    backups = [b for b in [backup(config_file), backup(scripts / "ardour_ultra_mcp.lua")] if b]
    normalized_roots = [str(p.expanduser().resolve()) for p in export_roots]
    config = {
        "protocol": 1,
        "token": previous["token"] if previous else secrets.token_hex(32),
        "export_roots": normalized_roots,
    }
    atomic_json(config_file, config)
    template = (
        importlib.resources.files("ardour_ultra_mcp.bridge")
        .joinpath("bridge.lua")
        .read_text(encoding="utf-8")
    )
    script = template.replace("@MAILBOX_LUA@", lua_string(str(root)))
    target = scripts / "ardour_ultra_mcp.lua"
    part = target.with_suffix(".lua.part")
    if part.is_symlink():
        raise DomainError(ErrorCode.PERMISSION_DENIED, "Installer temporary path is a symlink.")
    script_bytes = script.encode("utf-8")
    part.write_bytes(script_bytes)
    os.replace(part, target)
    atomic_json(
        root / "installation.json",
        {
            "protocol": 1,
            "script": str(target),
            "script_sha256": hashlib.sha256(script_bytes).hexdigest(),
            "config": str(configuration),
        },
    )
    return {
        "script": str(target),
        "mailbox": str(root),
        "ardour_candidates": find_ardour(),
        "backups": backups,
        "export_roots": normalized_roots,
        "required_ui_step": "In Ardour, Window > Scripting > Script Manager > Action Hooks, add Ardour Ultra MCP. Open a session, then run test-connection. Hook file I/O requires Preferences > Scripting > Sandbox all Lua scripts to be disabled; activate only this reviewed hook on trusted projects.",
        "connectivity": "not checked until hook activated",
    }


def uninstall(directory: Path | None = None) -> dict[str, Any]:
    root = private_directory(directory or mailbox_directory())
    record = json.loads(read_bounded(root / "installation.json", 16384))
    path = Path(record["script"])
    if path.name != "ardour_ultra_mcp.lua" or path.parent.name != "scripts":
        raise DomainError(ErrorCode.PERMISSION_DENIED, "Invalid installation manifest.")
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["script_sha256"]:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Installed script has user modifications.",
                "Back it up/remove it manually.",
            )
        backup(path)
        path.unlink()
    return {
        "removed_script": str(path),
        "mailbox_retained": str(root),
        "required_ui_step": "Remove the Ardour Ultra MCP action hook in Script Manager; mailbox and backups remain for review.",
    }
