"""Real standalone Ardour LuaSession integration; requires ARDOUR_LUA_PATH.

This verifies actual common/non_rt binding execution, not GUI EditorHook timing or
cross-platform DAW support. A temporary session is created; no user project is opened.
"""

import asyncio
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from ardour_ultra_mcp.backends.mailbox import MailboxBackend
from ardour_ultra_mcp.installers.install import install, lua_string
from ardour_ultra_mcp.security.paths import PathPolicy
from ardour_ultra_mcp.services.control import ControlService


async def main():
    executable = os.environ.get("ARDOUR_LUA_PATH")
    if not executable:
        raise SystemExit("Set ARDOUR_LUA_PATH to official Ardour luasession; no mock substitution.")
    with tempfile.TemporaryDirectory(prefix="ardour-ultra-e2e-") as folder:
        root = Path(folder)
        installed = install(root / "mailbox", root / "config", export_roots=(root,))
        script = root / "harness.lua"
        script.write_text(
            'io.stdout:setvbuf("no")\nlocal s=create_session('
            + lua_string(str(root / "session"))
            + ',"Ultra E2E",48000)\nassert(s)\nardour=function(x) end\ndofile('
            + lua_string(installed["script"])
            + ")\nlocal tick=factory()\nwhile true do tick(0,nil);sleep(.1) end\n"
        )
        log = root / "ardour.log"
        with log.open("w") as output:
            process = subprocess.Popen(
                [executable, str(script)], stdout=output, stderr=subprocess.STDOUT
            )
            service = None
            try:
                for _ in range(200):
                    if (root / "mailbox" / "heartbeat.json").exists():
                        break
                    if process.poll() is not None:
                        raise RuntimeError(log.read_text())
                    await asyncio.sleep(0.1)
                service = ControlService(
                    MailboxBackend(root / "mailbox"), PathPolicy((root,), (root,))
                )
                results = []

                async def check(command, args):
                    t = time.perf_counter()
                    result = await service.call(command, args)
                    results.append(
                        {
                            "command": command,
                            "duration_ms": (time.perf_counter() - t) * 1000,
                            "result": result.model_dump(mode="json"),
                        }
                    )
                    if not result.success:
                        reply = root / "mailbox" / "response.json"
                        if reply.exists():
                            Path("artifacts/ardour-last-reply.json").write_text(reply.read_text())
                        raise RuntimeError(json.dumps(results[-1]) + "\n" + log.read_text())
                    return result

                await check("ping", {})
                await check("get_session_info", {})
                track = await check("create_track", {"name": "Audio E2E", "kind": "audio"})
                track_id = track.data["id"]
                await check("set_track_gain", {"track_id": track_id, "gain_db": -4.25})
                await check("set_track_pan", {"track_id": track_id, "pan": -0.35})
                info = await check("get_track", {"track_id": track_id})
                assert (
                    abs(info.data["gain_db"] + 4.25) < 1e-5 and abs(info.data["pan"] + 0.35) < 1e-6
                )
                await check("set_track_mute", {"track_id": track_id, "enabled": True})
                await check("set_monitoring", {"track_id": track_id, "mode": "input"})
                await check("arm_track", {"track_id": track_id, "enabled": True})
                await check("list_tracks", {})
                await check("list_regions", {"track_id": track_id})
                await check("get_transport", {})
                await check("convert_position", {"position": {"unit": "bbt", "bar": 3, "beat": 1}})
                await check(
                    "set_tempo", {"position": {"unit": "bbt", "bar": 2, "beat": 1}, "bpm": 60}
                )
                converted = await check(
                    "convert_position", {"position": {"unit": "bbt", "bar": 3, "beat": 1}}
                )
                assert abs(converted.data["seconds"] - 6) < 1 / 48000
                await check(
                    "create_automation_points",
                    {
                        "track_id": track_id,
                        "control": "gain",
                        "unit": "linear_gain",
                        "points": [
                            {"position": {"unit": "samples", "samples": 0}, "value": 0.5},
                            {"position": {"unit": "samples", "samples": 48000}, "value": 0.75},
                        ],
                    },
                )
                await check("get_automation", {"track_id": track_id, "control": "gain"})
                await check(
                    "set_automation_mode", {"track_id": track_id, "control": "gain", "mode": "play"}
                )
                inventory = await check("list_available_plugins", {"limit": 1000})
                plugin = next(
                    p
                    for p in inventory.data["items"]
                    if p["format"] == "LV2" and not p["is_instrument"]
                )
                added = await check(
                    "add_plugin",
                    {"track_id": track_id, "plugin_id": plugin["plugin_id"], "format": "LV2"},
                )
                ref = {"track_id": track_id, "processor_id": added.data["processor_id"]}
                parameters = await check("get_plugin_parameters", ref)
                if parameters.data["items"]:
                    param = parameters.data["items"][0]
                    await check(
                        "set_plugin_parameters",
                        {
                            **ref,
                            "parameters": [
                                {
                                    "parameter_index": param["parameter_index"],
                                    "value": param["default"],
                                }
                            ],
                        },
                    )
                await check("list_plugin_presets", ref)
                await check("set_plugin_enabled", {**ref, "enabled": False})
                await check("list_ports", {})
                bus = await check("create_track", {"name": "Verb E2E", "kind": "bus"})
                send = await check(
                    "create_send",
                    {"track_id": track_id, "target_id": bus.data["id"], "gain_db": -6},
                )
                await check("list_sends", {"track_id": track_id})
                await check(
                    "set_send_gain",
                    {"track_id": track_id, "send_id": send.data["id"], "gain_db": -4.25},
                )
                await check(
                    "execute_batch",
                    {
                        "operations": [
                            {
                                "command": "set_track_gain",
                                "arguments": {"track_id": track_id, "gain_db": -2},
                            },
                            {
                                "command": "set_track_pan",
                                "arguments": {"track_id": track_id, "pan": 0.25},
                            },
                        ]
                    },
                )
                await check("get_meter_state", {"track_id": track_id})
                await check("create_snapshot", {"name": "Verified E2E"})
                await check("save_session", {})
                await check("remove_plugin", {**ref, "confirm_delete": True})
                await check(
                    "remove_send",
                    {"track_id": track_id, "send_id": send.data["id"], "confirm_delete": True},
                )
                await check("delete_track", {"track_id": track_id, "confirm_delete": True})
                Path("artifacts/ardour-luasession-e2e.json").write_text(
                    json.dumps(
                        {
                            "scope": "real Ardour LuaSession common/non_rt; no Editor GUI/OSC test; temporary Dummy engine session",
                            "executable_version": subprocess.check_output(
                                [executable, "-V"], text=True
                            ).strip(),
                            "checks": results,
                        },
                        indent=2,
                    )
                    + "\n"
                )
                print(
                    json.dumps(
                        {"passed": len(results), "scope": "real Ardour LuaSession common/non_rt"}
                    )
                )
            finally:
                if service:
                    await service.backend.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                Path("artifacts/ardour-luasession.log").write_text(log.read_text())


asyncio.run(main())
