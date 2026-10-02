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
      PBD={ID=function() error('unsafe ID constructor invoked') end}
      ARDOUR={LuaAPI={monotonic_time=function() return 123456 end}}
      Session={route_groups=function() return {iter=function() return function() return nil end end} end, path=function() return '/test' end, get_routes=function() return {iter=function() return function() return nil end end} end, actively_recording=function() return false end}
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
      Session={route_groups=function() return {iter=function() return function() return nil end end} end, path=function() return '/test' end, get_routes=function() return {iter=function() return function() return nil end end} end, route_by_id=function() return route end, actively_recording=function() return false end}
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


def test_lua_parameter_failure_restores_failed_current_value(tmp_path):
    result = install(tmp_path / "mailbox", tmp_path / "config")
    root = Path(result["mailbox"])
    lua = lupa.LuaRuntime()
    lua.execute("""
      ardour=function(x) end
      PBD={ID=function(x) return x end}
      values={[0]=10,[1]=20};failed=false
      local plugin={nth_parameter=function(self,i) return i,{[2]=true} end, parameter_is_control=function() return true end,
        parameter_is_input=function() return true end, get_parameter=function(self,i) return values[i] end,
        get_parameter_descriptor=function() return 0,{[2]={lower=0,upper=100,integer_step=false,toggled=false}} end}
      local proc={isnil=function() return false end,id=function() return {to_s=function() return '2' end} end,
        to_insert=function() return {isnil=function() return false end,plugin=function() return plugin end} end}
      local route={isnil=function() return false end,nth_processor=function(self,i) if i==0 then return proc end end}
      local function empty() return {iter=function() return function() return nil end end} end
      ARDOUR={ParameterDescriptor=function() return {} end, LuaAPI={monotonic_time=function() return 123456 end,
        set_processor_param=function(p,i,v) values[i]=v;if i==1 and not failed then failed=true;return false end;return true end}}
      Session={path=function() return '/test' end,get_routes=empty,route_groups=empty,route_by_id=function() return route end,
        processor_by_id=function() return proc end,actively_recording=function() return false end}
    """)
    lua.execute(Path(result["script"]).read_text())
    tick = lua.globals().factory(None)
    tick(0, None)
    heart = json.loads((root / "heartbeat.json").read_text())
    token = json.loads((root / "bridge-config.json").read_text())["token"]
    reply = request(
        (root, tick, heart["epoch"], token),
        command="set_plugin_parameters",
        arguments={
            "track_id": "1",
            "processor_id": "2",
            "parameters": [
                {"parameter_index": 0, "value": 50, "unit": "plugin_native"},
                {"parameter_index": 1, "value": 60, "unit": "plugin_native"},
            ],
        },
    )
    assert reply["result"]["error"]["code"] == "BACKEND_ERROR"
    assert lua.globals()["values"][0] == 10 and lua.globals()["values"][1] == 20


@pytest.mark.parametrize(
    "position",
    [{"unit": "samples", "samples": 9007199254740991}, {"unit": "seconds", "seconds": 1e10}],
)
def test_native_time_capacity_rejects_before_constructor(tmp_path, position):
    result = install(tmp_path / "mailbox", tmp_path / "config")
    root = Path(result["mailbox"])
    lua = lupa.LuaRuntime()
    lua.execute("""ardour=function(x) end
      ARDOUR={LuaAPI={monotonic_time=function() return 123456 end}}
      local function empty() return {iter=function() return function() return nil end end} end
      Session={path=function() return '/test' end,get_routes=empty,route_groups=empty,actively_recording=function() return false end,nominal_sample_rate=function() return 48000 end}
      Temporal={TempoMap={read=function() return {} end},superclock_ticks_per_second=function() return 1000000000 end,timepos_t=function() error('unsafe constructor invoked') end}
    """)
    lua.execute(Path(result["script"]).read_text())
    tick = lua.globals().factory(None)
    tick(0, None)
    heart = json.loads((root / "heartbeat.json").read_text())
    token = json.loads((root / "bridge-config.json").read_text())["token"]
    reply = request(
        (root, tick, heart["epoch"], token),
        command="convert_position",
        arguments={"position": position},
    )
    assert reply["result"]["error"]["code"] == "INVALID_TIME_POSITION"


@pytest.mark.parametrize(
    "object_id", ["1junk", "001", "-1", "1.0", "fake-route-1", "18446744073709551616", "2" * 21]
)
def test_native_ids_reject_truncation_aliases_before_constructor(lua_bridge, object_id):
    reply = request(lua_bridge, command="get_track", arguments={"track_id": object_id})
    assert reply["result"]["error"]["code"] == "VALIDATION_ERROR"
