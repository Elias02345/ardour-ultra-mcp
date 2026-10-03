"""The terminal setup contract, independent of an installed Ardour application."""

import json
from pathlib import Path

import pytest

from ardour_ultra_mcp.cli import main
from ardour_ultra_mcp.cli_output import diagnostics
from ardour_ultra_mcp.models.base import DomainError, ErrorCode, Result


def test_install_guidance_and_uninstall_preserve_private_config(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("ardour_ultra_mcp.cli.detect_versions", lambda: [])
    monkeypatch.setattr("ardour_ultra_mcp.installers.install.find_ardour", lambda: [])
    mailbox = tmp_path / "私の mailbox"
    options = ["--mailbox", str(mailbox)]
    assert main(["install", *options, "--ardour-config", str(tmp_path / "config")]) == 0
    output = capsys.readouterr().out
    token = json.loads((mailbox / "bridge-config.json").read_text())["token"]
    assert token not in output
    assert "not active yet" in output and "version could not be detected" in output
    assert "Action Hooks > New Hook" in output and "Window > Scripting" not in output
    assert "same --mailbox" in output and str(mailbox) in output
    assert main(["test-connection", *options]) == 2
    assert "ERROR [BRIDGE_NOT_RUNNING]" in capsys.readouterr().out
    assert main(["doctor", *options]) == 2
    assert "Connection: not ready" in capsys.readouterr().out
    assert main(["uninstall", *options]) == 0
    assert "retained" in capsys.readouterr().out
    assert (mailbox / "bridge-config.json").is_file()
    assert not (tmp_path / "config" / "scripts" / "ardour_ultra_mcp.lua").exists()


@pytest.mark.parametrize("command", ["doctor", "test-connection", "status", "capabilities"])
def test_simulator_diagnostics_cannot_claim_ardour_connection(command, capsys):
    assert main([command, "--backend", "fake"]) == 0
    output = capsys.readouterr().out
    assert "SIMULATED" in output
    assert "Connection OK" not in output


def test_real_connection_reports_engine_state_without_dumping_private_data():
    value = Result(data={"connected": True, "session_open": True, "engine_running": False})
    output = diagnostics("test-connection", value.model_dump(mode="json"), "lua")
    assert "Connection OK" in output and "Session: open" in output
    assert "Audio engine: stopped" in output


def test_cli_os_error_keeps_json_contract(tmp_path, monkeypatch, capsys):
    def failed(*args, **kwargs):
        raise PermissionError("private details")

    monkeypatch.setattr("ardour_ultra_mcp.cli.install", failed)
    monkeypatch.setattr("ardour_ultra_mcp.cli.detect_versions", lambda: [])
    assert main(["install", "--mailbox", str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert "ERROR [PERMISSION_DENIED]" in output and "private details" not in output
    assert main(["install", "--json", "--mailbox", str(tmp_path)]) == 2
    output = json.loads(capsys.readouterr().out)
    assert not output["success"] and output["error"]["type"] == "PermissionError"


def test_modified_script_refusal_is_actionable_in_both_formats(tmp_path, monkeypatch, capsys):
    def failed(*args, **kwargs):
        raise DomainError(ErrorCode.CONFLICT, "Script was edited.", "Back it up before removing.")

    monkeypatch.setattr("ardour_ultra_mcp.cli.uninstall", failed)
    assert main(["uninstall", "--mailbox", str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert "CONFLICT" in output and "Back it up before removing." in output
    assert main(["uninstall", "--mailbox", str(tmp_path), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "CONFLICT"


@pytest.mark.parametrize("client", ["claude", "claude-code", "codex", "generic"])
def test_configure_output_stays_copyable(client, capsys):
    assert main(["configure", client, "--backend", "fake"]) == 0
    output = capsys.readouterr().out
    if client == "codex":
        import tomllib

        configured = tomllib.loads(output)["mcp_servers"]["ardour_ultra"]
    else:
        configured = json.loads(output)["mcpServers"]["ardour-ultra"]
    assert Path(configured["command"]).is_absolute()
    assert "serve" in configured["args"]
    assert "--backend" in configured["args"] and "fake" in configured["args"]
