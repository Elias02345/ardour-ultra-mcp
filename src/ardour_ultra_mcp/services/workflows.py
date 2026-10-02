"""Small composable workflows with explicit changes and preserved partial results."""

from __future__ import annotations

import importlib.util
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import JsonValue

from ..models.base import DomainError, ErrorCode, Options, Result

Invoker = Callable[[str, dict[str, Any]], Awaitable[Result]]


async def ensure_bus(invoke: Invoker, a: dict[str, Any], options: Options) -> Result:
    offset, revision = 0, options.expected_revision
    candidates = []
    while True:
        page = await invoke(
            "list_tracks",
            {
                "name_filter": a["name"],
                "offset": offset,
                "limit": 1000,
                "expected_revision": revision,
            },
        )
        if not page.success:
            return page
        revision = page.revision_after
        items = page.data.get("items")
        if not isinstance(items, list):
            raise DomainError(ErrorCode.PROTOCOL_ERROR, "Route enumeration is malformed.")
        candidates += [t for t in items if isinstance(t, dict) and t.get("name") == a["name"]]
        next_offset = page.data.get("next_offset")
        if next_offset is None:
            break
        if not isinstance(next_offset, int) or not offset < next_offset <= 10000:
            raise DomainError(ErrorCode.BACKEND_UNSUPPORTED, "Workflow enumeration limit exceeded.")
        offset = next_offset
    if candidates:
        if len(candidates) != 1 or candidates[0].get("kind") != "bus":
            raise DomainError(
                ErrorCode.CONFLICT, "Name is ambiguous or belongs to a non-bus route."
            )
        bus = candidates[0]
        if bus.get("channels") != a["channels"]:
            raise DomainError(
                ErrorCode.CONFLICT, "Existing bus channel count differs or is unavailable."
            )
        return Result(
            data={"bus": bus, "created": False, "valid": True},
            revision_before=revision,
            revision_after=revision,
            warnings=page.warnings,
        )
    result = await invoke(
        "create_track",
        {**a, "kind": "bus", "expected_revision": revision, "dry_run": options.dry_run},
    )
    if result.success:
        result.data = {"bus": result.data, "created": not options.dry_run, "valid": True}
    return result


async def render_and_analyze(invoke: Invoker, a: dict[str, Any], options: Options) -> Result:
    missing: list[JsonValue] = [
        name
        for name in ("numpy", "scipy", "soundfile", "pyloudnorm")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise DomainError(
            ErrorCode.BACKEND_UNSUPPORTED,
            "Analysis dependencies are missing.",
            "Install the [analysis] extra before rendering.",
            missing=missing,
        )
    max_seconds = a.pop("max_seconds")
    rendered = await invoke("render_range", {**a, **options.model_dump()})
    if not rendered.success or options.dry_run:
        return rendered
    files = rendered.data.get("files")
    if not isinstance(files, list) or len(files) != 1 or not isinstance(files[0], str):
        return Result(
            success=False,
            data={"render": rendered.data, "analysis_completed": False},
            changed_objects=rendered.changed_objects,
            revision_before=rendered.revision_before,
            revision_after=rendered.revision_after,
            error=DomainError(
                ErrorCode.BACKEND_UNSUPPORTED,
                "Combined workflow requires exactly one rendered audio file.",
                "Analyze each returned file explicitly; exports are preserved.",
            ).detail,
        )
    # Export roots grant read permission to this exact completed render too.
    analysis = await invoke("analyze_audio_file", {"path": files[0], "max_seconds": max_seconds})
    steps: list[JsonValue] = [
        {"command": "render_range", "success": True},
        {"command": "analyze_audio_file", "success": analysis.success},
    ]
    return Result(
        success=analysis.success,
        data={
            "render": rendered.data,
            "analysis": analysis.data,
            "steps": steps,
            "analysis_completed": analysis.success,
            "atomic": False,
        },
        changed_objects=rendered.changed_objects,
        revision_before=rendered.revision_before,
        revision_after=rendered.revision_after,
        warnings=rendered.warnings
        + analysis.warnings
        + (
            []
            if analysis.success
            else [
                "Render files are preserved after analysis failure; do not overwrite or blindly rerender."
            ]
        ),
        error=analysis.error,
    )
