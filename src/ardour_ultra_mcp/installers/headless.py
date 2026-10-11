"""Headless Linux setup: activate the hook and create sessions without the Ardour GUI.

A server has no screen to click through Script Manager. These helpers use the same
documented persisted format that the native editor harness uses: Ardour's own
LuaSession compiles the reviewed bridge factory, and the result is stored as an
ActionHook in ``ui_scripts``. Only the installed, checksummed bridge is compiled;
no MCP command ever supplies Lua source.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

# Index of LuaTimerDS in gtk2_ardour/luasignal_syms.inc.h (after removing #if 0 blocks).
# The persisted hook stores its subscribed signals as a bit string with this index set.
KNOWN_TIMER_SIGNAL_INDEX = {9: 49}
HOOK_NAME = "Ardour Ultra MCP"
HOOK_ID = "987654321"

# Fixed LuaSession invocations of trusted, generated scripts; not a general shell tool.
import subprocess  # noqa: E402  # nosec B404

from ..models.base import DomainError, ErrorCode  # noqa: E402
from .install import lua_string  # noqa: E402


def timer_signal_index(major: int, signals_header: Path | None = None) -> int:
    """Return the LuaTimerDS bit position, from a source-matched header when given."""
    if signals_header is not None:
        text = re.sub(r"#if 0.*?#endif", "", signals_header.read_text(), flags=re.S)
        names = re.findall(r"^(?:STATIC|ENGINE|SESSION)\((\w+)", text, re.M)
        if "LuaTimerDS" not in names:
            raise DomainError(
                ErrorCode.OPERATION_NOT_SUPPORTED, "LuaTimerDS not found in signals header."
            )
        return names.index("LuaTimerDS")
    if major not in KNOWN_TIMER_SIGNAL_INDEX:
        raise DomainError(
            ErrorCode.OPERATION_NOT_SUPPORTED,
            f"No known signal index for Ardour {major}; pass --signals-header from the matching source.",
        )
    return KNOWN_TIMER_SIGNAL_INDEX[major]


def find_luasession(major: int = 9) -> str | None:
    """Find Ardour's LuaSession launcher.

    Prefer the packaged wrapper (e.g. ``ardour9-lua``): the raw ``luasession`` binary needs
    the wrapper's library and data environment to start.
    """
    for candidate in [shutil.which(f"ardour{major}-lua"), f"/usr/bin/ardour{major}-lua"]:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _run_lua(luasession: str, script: str, timeout: float = 60) -> None:
    """Run a trusted script; success is judged by a marker written after its last statement.

    Some LuaSession builds (observed: Debian 9.8.0+ds rebuilt on Ubuntu 26.04) abort with
    "exception not rethrown" during interpreter teardown after the script has finished, so the
    exit status alone cannot tell a completed script from a failed one.
    """
    with tempfile.TemporaryDirectory(prefix="ardour-ultra-headless-") as tmp:
        path = Path(tmp) / "run.lua"
        marker = Path(tmp) / "completed"
        path.write_text(
            script + "\nassert(io.open(" + lua_string(str(marker)) + ',"wb")):close()\n'
        )
        done = subprocess.run(  # nosec B603
            [luasession, str(path)], capture_output=True, text=True, timeout=timeout
        )
        completed = marker.exists()
    if not completed:
        raise DomainError(ErrorCode.BACKEND_ERROR, (done.stdout + done.stderr)[-2000:])


def compile_hook_state(luasession: str, bridge_script: Path) -> bytes:
    """Compile the installed bridge with Ardour's Lua and return the persisted hook state."""
    with tempfile.TemporaryDirectory(prefix="ardour-ultra-hook-") as tmp:
        state = Path(tmp) / "state"
        _run_lua(
            luasession,
            "ardour=function(x) end\ndofile("
            + lua_string(str(bridge_script))
            + ")\nlocal out=assert(io.open("
            + lua_string(str(state))
            + ',"wb"))\nlocal source=assert(io.open('
            + lua_string(str(bridge_script))
            + ',"rb")):read("*a")\nout:write("s={};s.n=",string.format("%q",'
            + lua_string(HOOK_NAME)
            + '),";s.s=",string.format("%q",source),";s.f=",string.format("%q",string.dump(factory,true)),";s.a={}")\nout:close()\n',
        )
        return state.read_bytes()


def activate_hook(
    config_dir: Path, bridge_script: Path, luasession: str, signal_index: int
) -> dict[str, Any]:
    """Write or replace the Ardour Ultra MCP action hook in ui_scripts, keeping other hooks."""
    state = compile_hook_state(luasession, bridge_script)
    target = config_dir / "ui_scripts"
    if target.exists():
        tree = ET.parse(target)
        root = tree.getroot()
    else:
        root = ET.Element("UIScripts")
        ET.SubElement(root, "ActionScript")
        tree = ET.ElementTree(root)
    hooks = root.find("ActionHooks")
    if hooks is None:
        hooks = ET.SubElement(root, "ActionHooks")
    for old in list(hooks):
        if old.get("name") == HOOK_NAME:
            hooks.remove(old)
    hook = ET.SubElement(
        hooks,
        "LuaCallback",
        {"lua": "Lua 5.3", "id": HOOK_ID, "name": HOOK_NAME, "signals": "1" + "0" * signal_index},
    )
    hook.text = base64.b64encode(state).decode()
    config_dir.mkdir(parents=True, exist_ok=True)
    part = target.with_name("ui_scripts.part")
    tree.write(part, encoding="utf-8", xml_declaration=True)
    os.replace(part, target)
    return {"ui_scripts": str(target), "hook": HOOK_NAME, "signal_index": signal_index}


def write_dummy_engine_config(
    config_dir: Path, sample_rate: int = 48000, buffer: int = 1024
) -> str:
    """Configure the silent Dummy backend with engine autostart for a display-less server.

    Leaves an existing config untouched so user preferences survive re-runs.
    """
    target = config_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / ".a9").touch()
    instant = config_dir / "instant.xml"
    if not instant.exists():
        instant.write_text("<instant><no-memory-warning/></instant>")
    if target.exists():
        return "kept"
    config = ET.Element("Ardour")
    settings = ET.SubElement(config, "Config")
    ET.SubElement(settings, "Option", {"name": "try-autostart-engine", "value": "1"})
    ET.SubElement(settings, "Option", {"name": "hide-dummy-backend", "value": "0"})
    states = ET.SubElement(
        ET.SubElement(ET.SubElement(config, "Extra"), "AudioMIDISetup"), "EngineStates"
    )
    ET.SubElement(
        states,
        "State",
        {
            "backend": "None (Dummy)",
            "driver": "Normal Speed",
            "device": "Silence",
            "input-device": "Silence",
            "output-device": "Silence",
            "sample-rate": str(sample_rate),
            "buffer-size": str(buffer),
            "n-periods": "0",
            "input-latency": "0",
            "output-latency": "0",
            "active": "1",
            "use-buffered-io": "0",
            "midi-option": "No MIDI I/O",
        },
    )
    ET.ElementTree(config).write(target, encoding="utf-8", xml_declaration=True)
    return "written"


def create_session(luasession: str, directory: Path, name: str, sample_rate: int = 48000) -> Path:
    """Create an empty Ardour session with Ardour's own LuaSession and return the .ardour file."""
    if directory.exists() and any(directory.iterdir()):
        raise DomainError(ErrorCode.CONFLICT, f"Session directory is not empty: {directory}")
    directory.parent.mkdir(parents=True, exist_ok=True)
    _run_lua(
        luasession,
        "local s=create_session("
        + lua_string(str(directory))
        + ","
        + lua_string(name)
        + f',{int(sample_rate)})\nassert(s)\nSession:save_state("",false,false,false)\nclose_session()\n',
    )
    session = directory / f"{name}.ardour"
    if not session.exists():
        raise DomainError(ErrorCode.BACKEND_ERROR, f"Ardour did not create {session}")
    return session
