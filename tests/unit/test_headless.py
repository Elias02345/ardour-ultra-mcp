import base64
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from ardour_ultra_mcp.installers import headless
from ardour_ultra_mcp.models.base import DomainError


def test_signal_index_from_header_ignores_disabled_blocks(tmp_path: Path) -> None:
    header = tmp_path / "luasignal_syms.inc.h"
    header.write_text(
        "#if 0\nSTATIC(Old, &x)\n#endif\nSTATIC(ConfigChanged, &a)\nENGINE(EngineRunning, b)\n"
        "SESSION(SessionLoad, c)\nSTATIC(LuaTimerDS, &LuaInstance::LuaTimerDS)\n"
    )
    assert headless.timer_signal_index(9, header) == 3


def test_signal_index_known_and_unknown_major() -> None:
    assert headless.timer_signal_index(9) == 49
    with pytest.raises(DomainError):
        headless.timer_signal_index(42)


def test_activate_hook_replaces_own_hook_and_keeps_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(headless, "compile_hook_state", lambda lua, script: b"state-v2")
    config = tmp_path / "ardour9"
    config.mkdir()
    (config / "ui_scripts").write_text(
        "<?xml version='1.0' encoding='utf-8'?><UIScripts><ActionScript/><ActionHooks>"
        '<LuaCallback name="Other" id="1" signals="1">b3RoZXI=</LuaCallback>'
        '<LuaCallback name="Ardour Ultra MCP" id="2" signals="1">b2xk</LuaCallback>'
        "</ActionHooks></UIScripts>"
    )
    result = headless.activate_hook(config, tmp_path / "bridge.lua", "/bin/true", 49)
    hooks = ET.parse(config / "ui_scripts").getroot().find("ActionHooks")
    assert hooks is not None
    names = [h.get("name") for h in hooks]
    assert names == ["Other", "Ardour Ultra MCP"]
    ours = hooks[1]
    assert ours.get("signals") == "1" + "0" * 49
    assert base64.b64decode(ours.text or "") == b"state-v2"
    assert result["signal_index"] == 49


def test_activate_hook_creates_ui_scripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(headless, "compile_hook_state", lambda lua, script: b"s")
    config = tmp_path / "fresh"
    headless.activate_hook(config, tmp_path / "bridge.lua", "/bin/true", 2)
    root = ET.parse(config / "ui_scripts").getroot()
    assert root.find("ActionScript") is not None
    hooks = root.find("ActionHooks")
    assert hooks is not None and len(hooks) == 1


def test_dummy_engine_config_is_written_once(tmp_path: Path) -> None:
    config = tmp_path / "ardour9"
    assert headless.write_dummy_engine_config(config) == "written"
    text = (config / "config").read_text()
    assert "None (Dummy)" in text and "try-autostart-engine" in text
    (config / "config").write_text("<Ardour>user</Ardour>")
    assert headless.write_dummy_engine_config(config) == "kept"
    assert (config / "config").read_text() == "<Ardour>user</Ardour>"


def test_create_session_refuses_non_empty_directory(tmp_path: Path) -> None:
    target = tmp_path / "Song"
    target.mkdir()
    (target / "keep.txt").write_text("x")
    with pytest.raises(DomainError):
        headless.create_session("/bin/true", target, "Song")


def test_create_session_reports_unfinished_script(tmp_path: Path) -> None:
    # Python cannot run the Lua script, so the completion marker is never written.
    with pytest.raises(DomainError):
        headless.create_session(sys.executable, tmp_path / "Song", "Song")


def test_missing_luasession_is_a_domain_error(tmp_path: Path) -> None:
    with pytest.raises(DomainError):
        headless.create_session(str(tmp_path / "missing-lua"), tmp_path / "Song", "Song")
