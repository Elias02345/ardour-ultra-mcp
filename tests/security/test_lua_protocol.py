import json
import time
from pathlib import Path

import lupa
import pytest

from ardour_ultra_mcp.installers.install import install


@pytest.fixture
def lua_bridge(tmp_path):
    result = install(tmp_path / "mailbox", tmp_path / "config")
    root = Path(result["mailbox"])
    lua = lupa.LuaRuntime()
    lua.execute("""
      ardour=function(x) end
      ARDOUR={LuaAPI={monotonic_time=function() return 123456 end}}
      Session={path=function() return '/test' end, get_routes=function() return {iter=function() return function() return nil end end} end, actively_recording=function() return false end}
    """)
    lua.execute(Path(result["script"]).read_text())
    tick = lua.globals().factory(None)
    tick(0, None)
    heart = json.loads((root / "heartbeat.json").read_text())
    token = json.loads((root / "bridge-config.json").read_text())["token"]
    return root, tick, heart["epoch"], token


def request(bridge, **updates):
    root, tick, epoch, token = bridge
    envelope = {
        "protocol": 1,
        "id": "ab" * 16,
        "epoch": epoch,
        "token": token,
        "expires": time.time() + 15,
        "command": "ping",
        "arguments": {},
        "options": {"dry_run": False, "confirm_delete": False},
    }
    envelope.update(updates)
    (root / "request.json").write_text(json.dumps(envelope))
    tick(0, None)
    return json.loads((root / "response.json").read_text())


def test_actual_lua_decoder_allowlist_and_correlation(lua_bridge):
    reply = request(lua_bridge)
    assert reply["result"]["success"] and reply["id"] == "ab" * 16
    assert not (lua_bridge[0] / "request.json").exists()
    rejected = request(lua_bridge, command='os.execute("bad")')
    assert rejected["result"]["error"]["code"] == "OPERATION_NOT_SUPPORTED"
    wrong = request(lua_bridge, token="0" * 64)
    assert wrong["result"]["error"]["code"] == "PROTOCOL_ERROR"
    expired = request(lua_bridge, expires=time.time() - 10)
    assert expired["result"]["error"]["code"] == "IPC_TIMEOUT"


@pytest.mark.parametrize(
    "payload",
    [
        "{} trailing",
        '{"a":1,"a":2}',
        "[1,]",
        '{"x":"\\uD800"}',
        '{"x":01}',
        '{"x":1.e3}',
        "[" * 60 + "]" * 60,
        'return os.execute("bad")',
    ],
)
def test_parser_rejects_malformed_without_code_execution(lua_bridge, payload):
    root, tick, _, _ = lua_bridge
    (root / "request.json").write_text(payload)
    tick(0, None)
    value = json.loads((root / "response.json").read_text())
    assert not value["result"]["success"] and value["result"]["error"]["code"] == "PROTOCOL_ERROR"


def test_unicode_surrogate_roundtrip_in_unknown_command(lua_bridge):
    result = request(lua_bridge, command="unknown😀")
    assert result["result"]["error"]["code"] == "OPERATION_NOT_SUPPORTED"


def test_lua_compensation_restores_even_failed_current_mutation(tmp_path):
    result = install(tmp_path / "mailbox", tmp_path / "config")
    root = Path(result["mailbox"])
    lua = lupa.LuaRuntime()
    lua.execute("""
      ardour=function(x) end
      PBD={ID=function(x) return x end,GroupControlDisposition={NoGroup=0}}
      ARDOUR={LuaAPI={monotonic_time=function() return 123456 end}}
      local function control(initial)
        return {value=initial, isnil=function() return false end, lower=function() return 0 end, upper=function() return 2 end, get_value=function(self) return self.value end, set_value=function(self,value) self.value=value;if self.fail then self.fail=false;error('injected native failure after update') end end}
      end
      test_gain=control(1);test_pan=control(.5)
      local route={isnil=function() return false end,gain_control=function() return test_gain end,pan_azimuth_control=function() return test_pan end}
      Session={path=function() return '/test' end, get_routes=function() return {iter=function() return function() return nil end end} end, route_by_id=function() return route end, actively_recording=function() return false end}
    """)
    lua.execute(Path(result["script"]).read_text())
    tick = lua.globals().factory(None)
    tick(0, None)
    heart = json.loads((root / "heartbeat.json").read_text())
    token = json.loads((root / "bridge-config.json").read_text())["token"]
    lua.globals().test_pan.fail = True
    reply = request(
        (root, tick, heart["epoch"], token),
        command="execute_batch",
        arguments={
            "name": "Injected failure",
            "operations": [
                {"command": "set_track_gain", "arguments": {"track_id": "1", "gain_db": -6}},
                {"command": "set_track_pan", "arguments": {"track_id": "1", "pan": -0.35}},
            ],
        },
    )
    assert not reply["result"]["success"] and reply["result"]["error"]["code"] == "BACKEND_ERROR"
    assert lua.globals().test_gain.value == pytest.approx(1)
    assert lua.globals().test_pan.value == pytest.approx(0.5)
