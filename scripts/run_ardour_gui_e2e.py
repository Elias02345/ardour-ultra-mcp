"""Official EditorHook integration in a disposable session. No GUI input automation.

Linux harness requires ARDOUR_GUI_PATH, ARDOUR_LUA_PATH, XVFB_PATH and source-matched
ARDOUR_SIGNALS_PATH. It installs a trusted test hook through Ardour's documented
persisted Lua callback format. Production installer leaves hook activation to user.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from xml.etree import ElementTree as ET

from audio_fixture import add_audio_fixture
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

from ardour_ultra_mcp.backends.mailbox import MailboxBackend
from ardour_ultra_mcp.backends.osc import OSCBackend
from ardour_ultra_mcp.installers.install import install, lua_string
from ardour_ultra_mcp.models.base import Result
from ardour_ultra_mcp.security.paths import PathPolicy
from ardour_ultra_mcp.services.control import ControlService


async def main() -> None:
    gui, lua, xvfb, symbols = [
        os.environ[k]
        for k in ["ARDOUR_GUI_PATH", "ARDOUR_LUA_PATH", "XVFB_PATH", "ARDOUR_SIGNALS_PATH"]
    ]
    major = int(os.environ.get("ARDOUR_MAJOR", "9"))
    with tempfile.TemporaryDirectory(prefix="ardour-ultra-editor-e2e-") as directory:
        root = Path(directory)
        cfg = root / "xdg" / f"ardour{major}"
        installed = install(root / "mailbox", cfg, major, (root,))
        script = root / "prepare.lua"
        # %q is Ardour's own Lua state-string representation. Only trusted installed
        # code is compiled here; MCP commands never accept Lua source or bytecode.
        script.write_text(
            "local s=create_session("
            + lua_string(str(root / "session"))
            + ',"Ultra Editor E2E",48000)\nassert(s)\nSession:new_audio_track(1,1,ARDOUR.RouteGroup(),1,"Audio Fixture",-1,ARDOUR.TrackMode.Normal,true,false)\nSession:save_state("",false,false,false)\nardour=function(x) end\ndofile('
            + lua_string(installed["script"])
            + ")\nlocal out=assert(io.open("
            + lua_string(str(root / "state"))
            + ',"wb"))\nlocal source=assert(io.open('
            + lua_string(installed["script"])
            + ',"rb")):read("*a")\nout:write("s={};s.n=",string.format("%q","Ardour Ultra MCP"),";s.s=",string.format("%q",source),";s.f=",string.format("%q",string.dump(factory,true)),";s.a={}")\nout:close()\n'
        )
        prep = subprocess.run([lua, str(script)], capture_output=True, text=True, timeout=30)
        if prep.returncode:
            raise RuntimeError(prep.stdout + prep.stderr)
        add_audio_fixture(root / "session" / "Ultra Editor E2E.ardour", root / "fixture.wav")
        text = Path(symbols).read_text()
        text = re.sub(r"#if 0.*?#endif", "", text, flags=re.S)
        names = re.findall(r"^(?:STATIC|ENGINE|SESSION)\((\w+)", text, re.M)
        index = names.index("LuaTimerDS")
        xml = ET.Element("UIScripts")
        ET.SubElement(xml, "ActionScript")
        hooks = ET.SubElement(xml, "ActionHooks")
        hook = ET.SubElement(
            hooks,
            "LuaCallback",
            {
                "lua": "Lua 5.3",
                "id": "987654321",
                "name": "Ardour Ultra MCP",
                "signals": "1" + "0" * index,
            },
        )
        hook.text = base64.b64encode((root / "state").read_bytes()).decode()
        ET.ElementTree(xml).write(cfg / "ui_scripts", encoding="utf-8", xml_declaration=True)
        (cfg / f".a{major}").touch()
        (cfg / "instant.xml").write_text("<instant><no-memory-warning/></instant>")
        config = ET.Element("Ardour")
        settings = ET.SubElement(config, "Config")
        ET.SubElement(settings, "Option", {"name": "try-autostart-engine", "value": "1"})
        ET.SubElement(settings, "Option", {"name": "hide-dummy-backend", "value": "0"})
        ET.SubElement(settings, "Option", {"name": "osc-port", "value": "3819"})
        protocols = ET.SubElement(config, "ControlProtocols")
        ET.SubElement(
            protocols,
            "Protocol",
            {
                "name": "Open Sound Control (OSC)",
                "active": "1",
                "config": "",
                "address-only": "0",
                "debugmode": "2",
            },
        )
        extra = ET.SubElement(config, "Extra")
        setup = ET.SubElement(extra, "AudioMIDISetup")
        states = ET.SubElement(setup, "EngineStates")
        ET.SubElement(
            states,
            "State",
            {
                "backend": "None (Dummy)",
                "driver": "Normal Speed",
                "device": "Silence",
                "input-device": "Silence",
                "output-device": "Silence",
                "sample-rate": "48000",
                "buffer-size": "1024",
                "n-periods": "0",
                "input-latency": "0",
                "output-latency": "0",
                "active": "1",
                "use-buffered-io": "0",
                "midi-option": "No MIDI I/O",
            },
        )
        ET.ElementTree(config).write(cfg / "config", encoding="utf-8", xml_declaration=True)
        env = dict(
            os.environ,
            XDG_CONFIG_HOME=str(root / "xdg"),
            DISPLAY=":91",
            ARDOUR_TRY_AUTOSTART_ENGINE="1",
            LANG="C.UTF-8",
        )
        display_log = (root / "display.log").open("w")
        display = subprocess.Popen(
            [xvfb, ":91", "-screen", "0", "1280x900x24", "-nolisten", "tcp"],
            stdout=display_log,
            stderr=subprocess.STDOUT,
        )
        output = (root / "gui.log").open("w")
        process = None
        results = []
        service = None
        osc = OSCBackend()
        try:
            await asyncio.sleep(0.5)
            process = subprocess.Popen(
                [
                    gui,
                    "-c",
                    "Unit-Test",
                    "--no-announcements",
                    "--no-splash",
                    str(root / "session" / "Ultra Editor E2E.ardour"),
                ],
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            for _ in range(300):
                heartbeat = root / "mailbox" / "heartbeat.json"
                if heartbeat.exists() and json.loads(heartbeat.read_text()).get("session_open"):
                    break
                if process.poll() is not None:
                    raise RuntimeError((root / "gui.log").read_text())
                await asyncio.sleep(0.1)
            else:
                windows = subprocess.run(
                    ["xwininfo", "-root", "-tree"], env=env, capture_output=True, text=True
                ).stdout
                raise RuntimeError(
                    "EditorHook did not become active.\n" + windows + (root / "gui.log").read_text()
                )
            service = ControlService(
                MailboxBackend(root / "mailbox", timeout=120), PathPolicy((root,), (root,))
            )

            async def check(command, arguments, target=None):
                start = time.perf_counter()
                result = await (target or service).call(command, arguments)
                results.append(
                    {
                        "command": command,
                        "duration_ms": (time.perf_counter() - start) * 1000,
                        "interface": getattr(target, "protocol", "domain_service"),
                        "result": result.model_dump(mode="json"),
                    }
                )
                if not result.success:
                    raise RuntimeError(json.dumps(results[-1]))
                return result

            await check("ping", {})
            audio_tracks = await check("list_tracks", {"name_filter": "Audio Fixture"})
            audio_id = audio_tracks.data["items"][0]["id"]
            audio_regions = await check("list_regions", {"track_id": audio_id, "kind": "audio"})
            assert audio_regions.data["total"] == 1
            audio_ref = {"track_id": audio_id, "region_id": audio_regions.data["items"][0]["id"]}
            await check("set_region_gain", {**audio_ref, "gain_db": -4.25})
            inspected = await check("get_region", audio_ref)
            assert abs(inspected.data["gain_db"] + 4.25) < 1e-5
            await check(
                "set_region_fades", {**audio_ref, "fade_in_samples": 128, "fade_out_samples": 256}
            )
            await check("set_region_mute", {**audio_ref, "enabled": True})
            await check("undo", {})
            assert (await check("get_region", audio_ref)).data["muted"] is False
            await check(
                "move_region", {**audio_ref, "position": {"unit": "samples", "samples": 24000}}
            )
            await check(
                "trim_region",
                {
                    **audio_ref,
                    "start": {"unit": "samples", "samples": 30000},
                    "end": {"unit": "samples", "samples": 48000},
                },
            )
            await check("set_region_lock", {**audio_ref, "enabled": True})
            denied = await service.call(
                "move_region", {**audio_ref, "position": {"unit": "samples", "samples": 0}}
            )
            assert not denied.success and denied.error.code == "PERMISSION_DENIED"
            await check("set_region_lock", {**audio_ref, "enabled": False})
            copied_audio = await check(
                "copy_region",
                {
                    **audio_ref,
                    "target_track_id": audio_id,
                    "name": "Audio copy",
                    "position": {"unit": "samples", "samples": 96000},
                },
            )
            assert (
                copied_audio.data["shared_audio_source"]
                and not copied_audio.data["independent_midi_source"]
            )
            await check(
                "delete_region",
                {
                    "track_id": audio_id,
                    "region_id": copied_audio.data["id"],
                    "confirm_delete": True,
                },
            )
            await check("undo", {})
            await check(
                "split_region", {**audio_ref, "position": {"unit": "samples", "samples": 36000}}
            )
            anchored = await check(
                "create_automation_points",
                {
                    "track_id": audio_id,
                    "control": "gain",
                    "unit": "linear_gain",
                    "points": [{"position": {"unit": "samples", "samples": 48000}, "value": 0.5}],
                },
            )
            assert (
                anchored.data["anchor_at_zero_added"] and anchored.data["actual_point_count"] == 2
            )
            anchor_curve = await check("get_automation", {"track_id": audio_id, "control": "gain"})
            assert [p["samples"] for p in anchor_curve.data["points"]] == [0, 48000]
            await check("undo", {})
            track = await check("create_track", {"name": "Bass", "kind": "midi"})
            track_id = track.data["id"]
            await check("rename_track", {"track_id": track_id, "name": "Bass verified"})
            inventory = await check(
                "list_available_plugins", {"instruments_only": True, "limit": 1000}
            )
            instrument = next(
                p
                for p in inventory.data["items"]
                if p["format"] == "LV2" and "Reasonable Synth" in p["name"]
            )
            await check(
                "add_plugin",
                {
                    "track_id": track_id,
                    "plugin_id": instrument["plugin_id"],
                    "format": instrument["format"],
                },
            )
            region = await check(
                "create_midi_region",
                {
                    "track_id": track_id,
                    "name": "Exact notes",
                    "start": {"unit": "bbt", "bar": 1, "beat": 1},
                    "end": {"unit": "bbt", "bar": 9, "beat": 1},
                },
            )
            ref = {"track_id": track_id, "region_id": region.data["id"]}
            native_status = await check("get_transport", {})
            assert native_status.data["engine_running"], native_status.data
            osc_service = ControlService(osc)
            await check("get_transport", {}, osc_service)
            await check("locate", {"position": {"unit": "samples", "samples": 48000}})
            await asyncio.sleep(0.5)
            native = await check("get_transport", {})
            observed = await check("get_transport", {}, osc_service)
            assert native.data["samples"] == 48000
            # OSC readback divergence is preserved in the dedicated native probe.
            # The optional adapter reports received values as unverified.
            await check("play", {})
            await asyncio.sleep(0.5)
            observed = await check("get_transport", {})
            assert observed.data["speed"] == 1
            await check("stop", {})
            await check("locate", {"position": {"unit": "samples", "samples": 0}})
            await asyncio.sleep(0.5)
            observed = await check("get_transport", {})
            assert observed.data["samples"] == 0 and observed.data["speed"] == 0
            notes = [
                {
                    "pitch": 48 + i % 12,
                    "velocity": 104,
                    "channel": 1,
                    "start_ticks": i * 240,
                    "duration_ticks": 240,
                }
                for i in range(100)
            ]
            await check("insert_midi_notes", {**ref, "notes": notes})
            listed = await check("list_midi_notes", {**ref, "limit": 1000})
            assert listed.data["total"] == 100
            next_page = await check("list_midi_notes", {**ref, "offset": 1, "limit": 1})
            assert next_page.data["model_fingerprint"] == listed.data["model_fingerprint"]
            assert (
                next_page.data["guard_cache"]["snapshots"]
                == listed.data["guard_cache"]["snapshots"]
            )
            await check(
                "insert_midi_notes",
                {
                    **ref,
                    "notes": [
                        dict(n, start_ticks=(i % 128) * 240) for i, n in enumerate(notes * 100)
                    ],
                },
            )
            dense = await check("list_midi_notes", {**ref, "limit": 1000})
            assert dense.data["total"] == 10100
            # Use current guarded snapshot after the dense insertion.
            listed = dense
            first = listed.data["items"][0]
            assert first["pitch"] == 48 and first["velocity"] == 104
            await check(
                "edit_midi_notes",
                {
                    **ref,
                    "model_fingerprint": listed.data["model_fingerprint"],
                    "replacements": [
                        {"note_ref": first["note_ref"], "note": {**notes[0], "pitch": 36}}
                    ],
                },
            )
            listed = await check("list_midi_notes", {**ref, "limit": 1000})
            assert any(n["pitch"] == 36 for n in listed.data["items"])
            await check("undo", {})
            listed = await check("list_midi_notes", {**ref, "limit": 1000})
            assert all(n["pitch"] != 36 for n in listed.data["items"])
            await check("redo", {})
            listed = await check("list_midi_notes", {**ref, "limit": 1000})
            await check(
                "delete_midi_notes",
                {
                    **ref,
                    "model_fingerprint": listed.data["model_fingerprint"],
                    "note_refs": [listed.data["items"][0]["note_ref"]],
                    "confirm_delete": True,
                },
            )
            await check("move_region", {**ref, "position": {"unit": "bbt", "bar": 2, "beat": 1}})
            copied = await check(
                "copy_region",
                {
                    **ref,
                    "target_track_id": track_id,
                    "name": "Independent copy",
                    "position": {"unit": "bbt", "bar": 10, "beat": 1},
                },
            )
            copy_ref = {"track_id": track_id, "region_id": copied.data["id"]}
            assert copied.data["independent_midi_source"] is True
            copy_notes = await check("list_midi_notes", {**copy_ref, "limit": 1})
            assert copy_notes.data["total"] == 10099
            await check("undo", {})
            regions = await check("list_regions", {"track_id": track_id})
            assert all(r["id"] != copy_ref["region_id"] for r in regions.data["items"])
            await check("redo", {})
            await check("insert_midi_notes", {**copy_ref, "notes": [{**notes[0], "pitch": 37}]})
            original_notes = await check("list_midi_notes", {**ref, "limit": 1})
            assert original_notes.data["total"] == 10099
            await check("split_region", {**ref, "position": {"unit": "bbt", "bar": 5, "beat": 1}})
            await check(
                "create_automation_points",
                {
                    "track_id": track_id,
                    "control": "gain",
                    "unit": "linear_gain",
                    "points": [
                        {"position": {"unit": "samples", "samples": 0}, "value": 0.5},
                        {"position": {"unit": "samples", "samples": 48000}, "value": 0.8},
                    ],
                },
            )
            await check(
                "create_automation_points",
                {
                    "track_id": track_id,
                    "control": "gain",
                    "unit": "linear_gain",
                    "replace": True,
                    "confirm_delete": True,
                    "points": [
                        {"position": {"unit": "samples", "samples": i * 100}, "value": 0.55}
                        for i in range(10000)
                    ],
                },
            )
            dense_curve = await check("get_automation", {"track_id": track_id, "control": "gain"})
            assert len(dense_curve.data["points"]) == 10000
            await check("undo", {})
            restored = await check("get_automation", {"track_id": track_id, "control": "gain"})
            assert len(restored.data["points"]) == 2
            await check("undo", {})
            await check("save_session", {})
            rendered = await check(
                "render_range",
                {
                    "start": {"unit": "bbt", "bar": 2, "beat": 1},
                    "end": {"unit": "bbt", "bar": 3, "beat": 1},
                    "output_directory": str(root / "export"),
                    "name": "verified",
                    "preset_id": "75969a1c-3133-4694-864b-a1fa50e43348",
                },
            )
            analysis = await check("analyze_audio_file", {"path": rendered.data["files"][0]})
            assert (
                analysis.data["peak_dbfs"] is not None
                and analysis.data["integrated_lufs"] is not None
            )
            await check(
                "compare_audio_files",
                {"first": rendered.data["files"][0], "second": rendered.data["files"][0]},
            )
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "ardour_ultra_mcp",
                    "serve",
                    "--mailbox",
                    str(root / "mailbox"),
                    "--media-root",
                    str(root),
                    "--export-root",
                    str(root),
                ],
            )
            async with Client(parameters) as client:

                class WireCalls:
                    protocol = "mcp_stdio"

                    async def call(self, command, arguments):
                        response = await client.call_tool(command, {"request": arguments})
                        return Result.model_validate(response.structured_content)

                wire = WireCalls()
                await check("get_server_info", {}, wire)
                await check("get_capabilities", {}, wire)
                await check("get_session_info", {}, wire)
                routes = await check("list_tracks", {}, wire)
                master_id = next(r["id"] for r in routes.data["items"] if r["kind"] == "master")
                await check("set_track_gain", {"track_id": master_id, "gain_db": -12}, wire)
                master = await check("get_track", {"track_id": master_id}, wire)
                assert abs(master.data["gain_db"] + 12) < 1e-5
                combined = await check(
                    "render_and_analyze",
                    {
                        "start": {"unit": "bbt", "bar": 2, "beat": 1},
                        "end": {"unit": "bbt", "bar": 3, "beat": 1},
                        "output_directory": str(root / "combined-export"),
                        "name": "combined",
                        "preset_id": "75969a1c-3133-4694-864b-a1fa50e43348",
                    },
                    wire,
                )
                assert combined.data["analysis_completed"]
                assert combined.data["analysis"]["peak_dbfs"] < analysis.data["peak_dbfs"] - 6
                compared = await check(
                    "compare_audio_files",
                    {
                        "first": rendered.data["files"][0],
                        "second": combined.data["render"]["files"][0],
                    },
                    wire,
                )
                assert compared.data["delta_second_minus_first"]["peak_dbfs"] < -6
            print(
                json.dumps(
                    {"passed": len(results), "scope": "real EditorHook, no GUI input automation"}
                )
            )
        finally:
            await osc.close()
            if service:
                await service.backend.close()
            if process:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            display.terminate()
            display.wait(timeout=10)
            output.close()
            display_log.close()
            Path("artifacts/ardour-editor-e2e.json").write_text(
                json.dumps(
                    {
                        "scope": "real Linux Ardour EditorHook on Dummy engine; no GUI input automation",
                        "executable_version": subprocess.check_output(
                            [lua, "-V"], text=True
                        ).strip(),
                        "checks": results,
                    },
                    indent=2,
                )
                + "\n"
            )
            Path("artifacts/ardour-editor.log").write_text((root / "gui.log").read_text())


if __name__ == "__main__":
    asyncio.run(main())
