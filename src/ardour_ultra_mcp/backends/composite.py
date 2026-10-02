from pydantic import JsonValue

from ..models.base import Options, Result
from .base import Backend
from .osc import OSCBackend


class CompositeBackend:
    """Lua owns edits; OSC telemetry is available in capability/status metadata."""

    name = "composite"

    def __init__(self, lua: Backend, osc: OSCBackend) -> None:
        self.lua, self.osc = lua, osc

    async def execute(
        self, command: str, arguments: dict[str, JsonValue], options: Options
    ) -> Result:
        return await self.lua.execute(command, arguments, options)

    async def capabilities(self) -> dict[str, JsonValue]:
        value = await self.lua.capabilities()
        return {
            **value,
            "backend": self.name,
            "osc": await self.osc.capabilities(),
            "mutation_backend": "lua",
            "automatic_fallback": False,
        }

    async def close(self) -> None:
        await self.lua.close()
        await self.osc.close()
