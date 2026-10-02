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
import tempfile
import time
from pathlib import Path
from xml.etree import ElementTree as ET

from ardour_ultra_mcp.backends.mailbox import MailboxBackend
from ardour_ultra_mcp.installers.install import install, lua_string
from ardour_ultra_mcp.security.paths import PathPolicy
from ardour_ultra_mcp.services.control import ControlService


async def main() -> None:
    gui, lua, xvfb, symbols = [
        os.environ[k]
        for k in ["ARDOUR_GUI_PATH", "ARDOUR_LUA_PATH", "XVFB_PATH", "ARDOUR_SIGNALS_PATH"]
    ]
    major = int(os.environ.get("ARDOUR_MAJOR", "8"))
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
            + ',"Ultra Editor E2E",48000)\nassert(s)\nSession:save_state("",false,false,false)\nardour=function(x) end\ndofile('
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

            async def check(command, arguments):
                start = time.perf_counter()
                result = await service.call(command, arguments)
                results.append(
                    {
                        "command": command,
                        "duration_ms": (time.perf_counter() - start) * 1000,
                        "result": result.model_dump(mode="json"),
                    }
                )
                if not result.success:
                    raise RuntimeError(json.dumps(results[-1]))
                return result

            await check("ping", {})
            track = await check("create_track", {"name": "Bass", "kind": "midi"})
            track_id = track.data["id"]
            await check("rename_track", {"track_id": track_id, "name": "Bass verified"})
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
            listed = await check("list_midi_notes", ref)
            assert listed.data["items"][0]["pitch"] == 36
            await check("undo", {})
            listed = await check("list_midi_notes", ref)
            assert listed.data["items"][0]["pitch"] == 48
            await check("redo", {})
            listed = await check("list_midi_notes", ref)
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
            await check("undo", {})
            await check("save_session", {})
            await check(
                "render_range",
                {
                    "start": {"unit": "samples", "samples": 0},
                    "end": {"unit": "samples", "samples": 48000},
                    "output_directory": str(root / "export"),
                    "name": "verified",
                },
            )
            print(
                json.dumps(
                    {"passed": len(results), "scope": "real EditorHook, no GUI input automation"}
                )
            )
        finally:
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
                        "checks": results,
                    },
                    indent=2,
                )
                + "\n"
            )
            Path("artifacts/ardour-editor.log").write_text((root / "gui.log").read_text())


if __name__ == "__main__":
    asyncio.run(main())
