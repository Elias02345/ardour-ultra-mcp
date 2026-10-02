import json
import sys

import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

from ardour_ultra_mcp.server import create_server
from ardour_ultra_mcp.services.catalog import SPECS


async def test_official_sdk_tool_schemas_structured_errors_resources(service):
    async with Client(create_server(service)) as client:
        assert client.server_info.version == "0.1.0"
        assert not client.server_capabilities.resources.subscribe
        listing = await client.list_tools()
        assert len(listing.tools) == len(SPECS)
        tool = next(t for t in listing.tools if t.name == "insert_midi_notes")
        assert tool.input_schema["properties"]["request"] and tool.output_schema
        info = await client.call_tool("get_server_info", {"request": {}})
        assert not info.is_error and info.structured_content["data"]["mcp_sdk"].startswith("2.")
        bad = await client.call_tool("get_track", {"request": {"track_id": "missing"}})
        assert bad.is_error and bad.structured_content["error"]["code"] == "OBJECT_NOT_FOUND"
        resources = await client.list_resources()
        assert len(resources.resources) == 7
        content = await client.read_resource("ardour://capabilities")
        parsed = json.loads(content.contents[0].text)
        assert parsed["data"]["simulated"]
        prompts = await client.list_prompts()
        assert len(prompts.prompts) == 1


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_real_stdio_subprocess_no_protocol_log_corruption(mode):
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "ardour_ultra_mcp", "serve", "--backend", "fake"]
    )
    async with Client(parameters, mode=mode) as client:
        info = await client.call_tool("get_server_info", {"request": {}})
        assert info.structured_content["success"]
        created = await client.call_tool(
            "create_track", {"request": {"name": "Bass", "kind": "midi"}}
        )
        assert not created.is_error and created.structured_content["data"]["id"].startswith(
            "fake-route-"
        )
        listing = await client.list_tools()
        assert len(listing.tools) == len(SPECS)
