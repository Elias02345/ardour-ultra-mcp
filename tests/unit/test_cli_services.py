import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from ardour_ultra_mcp.backends.composite import CompositeBackend
from ardour_ultra_mcp.backends.fake import FakeBackend
from ardour_ultra_mcp.backends.osc import OSCBackend
from ardour_ultra_mcp.cli import client_configuration, main, make_service, parser
from ardour_ultra_mcp.models.base import DomainError, ErrorCode, Options, Result
from ardour_ultra_mcp.security.paths import PathPolicy
from ardour_ultra_mcp.services.control import ControlService


def test_cli_diagnostics_and_safe_configuration(capsys, tmp_path):
    for command in ["doctor", "status", "capabilities", "test-connection"]:
        assert main([command, "--backend", "fake", "--json"]) == 0
        value = json.loads(capsys.readouterr().out)
        assert value["success"]
    for client in ["claude", "claude-code", "generic", "codex"]:
        args = parser().parse_args(
            [
                "configure",
                client,
                "--backend",
                "fake",
                "--mailbox",
                str(tmp_path / "ユニ code"),
                "--media-root",
                str(tmp_path),
            ]
        )
        value = client_configuration(args)
        if client == "codex":
            import tomllib

            assert tomllib.loads(value)["mcp_servers"]["ardour_ultra"]["args"][0] in {"serve", "-m"}
        else:
            assert "ardour-ultra" in json.loads(value)["mcpServers"]


def test_cli_install_uninstall_and_missing_connection(capsys, tmp_path):
    mailbox = tmp_path / "mailbox"
    assert (
        main(
            [
                "install",
                "--mailbox",
                str(mailbox),
                "--ardour-config",
                str(tmp_path / "config"),
                "--json",
            ]
        )
        == 0
    )
    installed = json.loads(capsys.readouterr().out)
    assert Path(installed["script"]).is_file()
    assert main(["doctor", "--mailbox", str(mailbox), "--json"]) == 2
    assert not json.loads(capsys.readouterr().out)["data"]["connectivity"]["success"]
    assert main(["uninstall", "--mailbox", str(mailbox), "--json"]) == 0
    assert not Path(installed["script"]).exists()
    assert json.loads(capsys.readouterr().out)["mailbox_retained"] == str(mailbox)


def test_cli_invalid_timeout_and_version(capsys):
    with pytest.raises(SystemExit) as raised:
        main(["serve", "--timeout", "0"])
    assert raised.value.code == 2
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0
    assert "0.1.0" in capsys.readouterr().out


def test_missing_bridge_starts_diagnostic_service(tmp_path):
    args = parser().parse_args(["serve", "--mailbox", str(tmp_path / "missing")])
    service = make_service(args)
    assert service.backend.name == "lua"


async def test_composite_never_silently_falls_back():
    fake, osc = FakeBackend(), OSCBackend(timeout=0.01)
    composite = CompositeBackend(fake, osc)
    cap = await composite.capabilities()
    assert cap["automatic_fallback"] is False and cap["mutation_backend"] == "lua"
    assert (await composite.execute("ping", {}, Options())).data["simulated"]
    result = await ControlService(composite).call("get_track", {"track_id": "missing"})
    assert result.error.code == ErrorCode.OBJECT_NOT_FOUND and osc.transport is None
    await composite.close()


async def test_local_audio_services_preflight_and_compare(tmp_path):
    path = tmp_path / "a.wav"
    signal = 0.1 * np.sin(2 * np.pi * 1000 * np.arange(48000) / 48000)
    sf.write(path, signal, 48000, subtype="FLOAT")
    service = ControlService(FakeBackend(), PathPolicy((tmp_path,), (tmp_path,)))
    preview = await service.call("analyze_audio_file", {"path": str(path), "dry_run": True})
    assert preview.success and preview.data["valid"]
    analysis = await service.call("analyze_audio_file", {"path": str(path)})
    assert analysis.success and analysis.data["peak_dbfs"] == pytest.approx(-20, abs=0.01)
    compared = await service.call("compare_audio_files", {"first": str(path), "second": str(path)})
    assert compared.success
    denied = await service.call("analyze_audio_file", {"path": "/not/allowed.wav"})
    assert denied.error.code == ErrorCode.PERMISSION_DENIED


class ExportBackend:
    name = "export-fixture"

    def __init__(self, fail_preflight=False, empty=False):
        self.fail_preflight, self.empty = fail_preflight, empty
        self.calls = []

    async def capabilities(self):
        return {"commands": ["render_range"]}

    async def execute(self, command, arguments, options):
        self.calls.append(options.dry_run)
        if options.dry_run:
            if self.fail_preflight:
                raise DomainError(ErrorCode.INVALID_TIME_POSITION, "Test preflight failure")
            return Result(data={"valid": True})
        if not self.empty:
            sf.write(Path(arguments["output_directory"]) / "render.wav", np.zeros(48000), 48000)
        return Result(data={})

    async def close(self):
        pass


async def test_export_preflight_before_filesystem_mutation(tmp_path):
    args = {
        "start": {"unit": "samples", "samples": 0},
        "end": {"unit": "samples", "samples": 48000},
        "output_directory": str(tmp_path / "new"),
        "name": "mix",
    }
    unavailable = ControlService(FakeBackend(), PathPolicy((), (tmp_path,)))
    assert (
        await unavailable.call("render_range", args)
    ).error.code == ErrorCode.BACKEND_UNSUPPORTED
    assert not (tmp_path / "new").exists()
    broken = ExportBackend(fail_preflight=True)
    assert not (
        await ControlService(broken, PathPolicy((), (tmp_path,))).call("render_range", args)
    ).success
    assert broken.calls == [True] and not (tmp_path / "new").exists()
    good = ExportBackend()
    service = ControlService(good, PathPolicy((), (tmp_path,)))
    assert (await service.call("render_range", {**args, "dry_run": True})).success
    assert not (tmp_path / "new").exists()
    result = await service.call("render_range", args)
    assert result.success and len(result.data["files"]) == 1
    assert (await service.call("render_range", args)).error.code == ErrorCode.FILE_EXISTS


async def test_export_empty_result_is_failure(tmp_path):
    service = ControlService(ExportBackend(empty=True), PathPolicy((), (tmp_path,)))
    result = await service.call(
        "render_range",
        {
            "start": {"unit": "seconds", "seconds": 0},
            "end": {"unit": "seconds", "seconds": 1},
            "name": "mix",
            "output_directory": str(tmp_path / "empty"),
        },
    )
    assert result.error.code == ErrorCode.BACKEND_ERROR


async def test_render_and_analyze_preserves_completed_export_on_failure(tmp_path, monkeypatch):
    service = ControlService(ExportBackend(), PathPolicy((), (tmp_path,)))
    request = {
        "start": {"unit": "seconds", "seconds": 0},
        "end": {"unit": "seconds", "seconds": 1},
        "name": "mix",
        "output_directory": str(tmp_path / "loop"),
    }
    dry = await service.call("render_and_analyze", {**request, "dry_run": True})
    assert dry.success and not (tmp_path / "loop").exists()
    result = await service.call("render_and_analyze", request)
    assert result.success and result.data["analysis_completed"] and result.data["atomic"] is False
    assert result.data["analysis"]["metadata"]["sample_rate_hz"] == 48000
    failed = await service.call(
        "render_and_analyze",
        {**request, "output_directory": str(tmp_path / "failed-analysis"), "max_seconds": 0.1},
    )
    assert not failed.success and failed.data["analysis_completed"] is False
    assert Path(failed.data["render"]["files"][0]).exists()
    assert failed.warnings
    monkeypatch.setattr(
        "ardour_ultra_mcp.services.workflows.importlib.util.find_spec", lambda name: None
    )
    missing = await service.call(
        "render_and_analyze",
        {**request, "output_directory": str(tmp_path / "missing-dependencies")},
    )
    assert missing.error.code == ErrorCode.BACKEND_UNSUPPORTED
    assert not (tmp_path / "missing-dependencies").exists()


def test_discovered_ardour_version_probe(monkeypatch):
    import subprocess

    from ardour_ultra_mcp.installers.platforms import detect_versions

    calls = []

    def run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        if arguments[0] == "missing":
            raise FileNotFoundError
        if arguments[0] == "slow":
            raise subprocess.TimeoutExpired(arguments, 3)
        return subprocess.CompletedProcess(
            arguments, 0, stdout="Ardour9.8.0~ds (build info)", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", run)
    results = detect_versions(["ardour with spaces", "missing", "slow"])
    assert results[0]["major"] == 9 and results[0]["verified"]
    assert not results[1]["verified"] and not results[2]["verified"]
    assert calls[0][0] == ["ardour with spaces", "--version"] and not calls[0][1].get("shell")
