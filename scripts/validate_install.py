"""Run with the Python from a clean wheel installation, outside an editable checkout."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

import ardour_ultra_mcp
from ardour_ultra_mcp.installers.install import install


async def main() -> None:
    module = Path(ardour_ultra_mcp.__file__).resolve()
    assert Path(sys.prefix).resolve() in module.parents, (
        "Requires a non-editable wheel installation"
    )
    checks: list[str] = []
    for command in ["doctor", "capabilities", "status", "test-connection"]:
        run = subprocess.run(
            [sys.executable, "-m", "ardour_ultra_mcp", command, "--backend", "fake", "--json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        json.loads(run.stdout)
        checks.append(f"CLI {command}")
    with tempfile.TemporaryDirectory(prefix="ultra-wheel-λ ") as tmp:
        root = Path(tmp)
        installed = install(root / "mailbox", root / "config")
        script = Path(installed["script"]).read_text()
        assert "@MAILBOX_LUA@" not in script and "function factory" in script
        checks.append("packaged Lua template / Unicode and spaces installation")
        import numpy as np
        import soundfile as sf

        rate = 48000
        sf.write(root / "tone.wav", 0.25 * np.sin(2 * np.pi * 1000 * np.arange(rate) / rate), rate)
        for mode in ["auto", "legacy"]:
            params = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "ardour_ultra_mcp",
                    "serve",
                    "--backend",
                    "fake",
                    "--media-root",
                    str(root),
                ],
            )
            async with Client(params, mode=mode) as client:
                tools = await client.list_tools()
                assert len(tools.tools) == 80
                resources = await client.list_resources()
                assert len(resources.resources) == 7
                prompts = await client.list_prompts()
                assert len(prompts.prompts) == 1
                made = await client.call_tool(
                    "create_track", {"request": {"name": "Bass λ", "kind": "midi"}}
                )
                assert made.structured_content["success"]
                tid = made.structured_content["data"]["id"]
                region = await client.call_tool(
                    "create_midi_region",
                    {
                        "request": {
                            "track_id": tid,
                            "name": "Dense wire batch",
                            "start": {"unit": "samples", "samples": 0},
                            "end": {"unit": "quarter_ticks", "ticks": 3200000},
                        }
                    },
                )
                inserted = await client.call_tool(
                    "insert_midi_notes",
                    {
                        "request": {
                            "track_id": tid,
                            "region_id": region.structured_content["data"]["id"],
                            "notes": [
                                {
                                    "pitch": 48 + i % 12,
                                    "velocity": 104,
                                    "channel": 1,
                                    "start_ticks": i * 240,
                                    "duration_ticks": 240,
                                }
                                for i in range(10000)
                            ],
                        }
                    },
                )
                assert (
                    not inserted.is_error
                    and inserted.structured_content["data"]["inserted_count"] == 10000
                )
                points = await client.call_tool(
                    "create_automation_points",
                    {
                        "request": {
                            "track_id": tid,
                            "control": "gain",
                            "unit": "linear_gain",
                            "points": [
                                {"position": {"unit": "samples", "samples": i * 100}, "value": 0.5}
                                for i in range(10000)
                            ],
                        }
                    },
                )
                assert (
                    not points.is_error
                    and len(points.structured_content["data"]["points"]) == 10000
                )
                gain = await client.call_tool(
                    "set_track_gain", {"request": {"track_id": tid, "gain_db": -4.25}}
                )
                assert gain.structured_content["success"]
                got = await client.call_tool("get_track", {"request": {"track_id": tid}})
                assert got.structured_content["data"]["gain_db"] == -4.25
                error = await client.call_tool("get_track", {"request": {"track_id": "missing"}})
                assert (
                    error.is_error
                    and error.structured_content["error"]["code"] == "OBJECT_NOT_FOUND"
                )
                analyzed = await client.call_tool(
                    "analyze_audio_file", {"request": {"path": str(root / "tone.wav")}}
                )
                assert (
                    not analyzed.is_error
                    and analyzed.structured_content["data"]["integrated_lufs"] is not None
                )
                checks.append(
                    f"official Client {mode} STDIO discovery/dense MIDI and automation/mutation/readback/error/analysis"
                )
    report = {
        "package": version("ardour-ultra-mcp"),
        "mcp": version("mcp"),
        "python": sys.version.split()[0],
        "installed_module": str(module),
        "checks": checks,
        "passed": len(checks),
        "scope": "clean Linux wheel installation; fake backend and real offline audio analysis; not native Ardour",
    }
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
