from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context
from mcp_types import CallToolResult, TextContent, ToolAnnotations

from . import __version__
from .models.base import Options, Result
from .services.catalog import SPECS, ToolSpec
from .services.control import ControlService

ToolResponse = Annotated[CallToolResult, Result]


def handler_for(service: ControlService, spec: ToolSpec) -> Callable[..., Awaitable[ToolResponse]]:
    async def handler(request: Options, ctx: Context) -> ToolResponse:
        if spec.category in {"analysis", "export"} or spec.name == "render_and_analyze":
            await ctx.report_progress(
                0, 1, "Validating and processing bounded local audio operation"
            )
        result = await service.call(spec.name, request)
        if spec.category in {"analysis", "export"} or spec.name == "render_and_analyze":
            await ctx.report_progress(
                1, 1, "Completed" if result.success else "Failed; inspect structured error"
            )
        payload = result.model_dump(mode="json")
        return CallToolResult(
            content=[
                TextContent(
                    type="text", text=json.dumps(payload, ensure_ascii=False, allow_nan=False)
                )
            ],
            structured_content=payload,
            is_error=not result.success,
        )

    handler.__name__ = spec.name
    handler.__doc__ = spec.description
    handler.__annotations__ = {"request": spec.request, "ctx": Context, "return": ToolResponse}
    return handler


def create_server(service: ControlService) -> MCPServer[Any]:
    @asynccontextmanager
    async def lifespan(server: MCPServer[Any]) -> AsyncIterator[None]:
        try:
            yield None
        finally:
            await service.backend.close()

    server = MCPServer(
        "ardour-ultra-mcp",
        instructions="Inspect ardour://capabilities and session state before editing. Units are explicit. Backend fake is simulated. Native undo and compensation have different scopes. Never retry an OUTCOME_UNCERTAIN mutation automatically.",
        lifespan=lifespan,
        version=__version__,
        subscriptions=False,
    )
    for spec in SPECS:
        server.add_tool(
            handler_for(service, spec),
            name=spec.name,
            description=spec.description,
            annotations=ToolAnnotations(
                read_only_hint=not spec.mutates,
                destructive_hint=spec.destructive,
                idempotent_hint=spec.name.startswith(("set_", "ensure_")) or not spec.mutates,
                open_world_hint=False,
            ),
            structured_output=True,
        )
    resources = {
        "session": "get_session_info",
        "tracks": "list_tracks",
        "routing": "list_ports",
        "timeline": "get_transport",
        "plugins": "list_available_plugins",
        "capabilities": "get_capabilities",
        "status": "doctor",
    }

    def resource_for(command: str) -> Callable[[], Awaitable[str]]:
        async def read() -> str:
            return (await service.call(command, {})).model_dump_json()

        return read

    for name, command in resources.items():
        server.resource(
            f"ardour://{name}",
            name=name,
            description=f"Read current {name}; collections are bounded first pages, use tools for further pages.",
            mime_type="application/json",
        )(resource_for(command))

    @server.prompt()
    def precise_production_workflow() -> str:
        """Inspection, exact editing, rendering and measured iteration using available capabilities."""
        return "Inspect capabilities and session. Select actual inventory plugin IDs. Use stable route/region/processor IDs. Convert BBT via convert_position, then use source-relative 1920 quarter ticks for MIDI batches. Inspect plugin native ranges and units. Preflight changes with dry_run; use expected_revision only within documented scope. Batch MIDI/automation. Render into a new allowed directory, analyze offline, compare passes. Inspect changed_objects. Stop and refresh after OUTCOME_UNCERTAIN. Never claim simulated output is Ardour audio."

    return server
