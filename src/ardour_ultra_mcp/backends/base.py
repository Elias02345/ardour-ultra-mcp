from typing import Protocol

from pydantic import JsonValue

from ..models.base import Options, Result


class Backend(Protocol):
    name: str

    async def execute(
        self, command: str, arguments: dict[str, JsonValue], options: Options
    ) -> Result: ...

    async def capabilities(self) -> dict[str, JsonValue]: ...

    async def close(self) -> None: ...
