"""Deterministic, explicitly simulated backend; it never impersonates a real DAW."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from typing import Any

from pydantic import JsonValue

from ..models.base import Change, DomainError, ErrorCode, Options, Result
from ..services.catalog import CATALOG, COMPENSABLE, UNSUPPORTED
from ..state.timeline import Timeline
from .fake_editing import edit_command
from .fake_plugins import plugin_command


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def paginate(values: list[dict[str, Any]], a: dict[str, Any]) -> dict[str, Any]:
    filtered = [
        v
        for v in values
        if a.get("name_filter", "").casefold()
        in (v.get("name", "") + v.get("category", "")).casefold()
    ]
    offset, limit = a.get("offset", 0), a.get("limit", 100)
    return {
        "items": copy.deepcopy(filtered[offset : offset + limit]),
        "total": len(filtered),
        "offset": offset,
        "limit": limit,
        "next_offset": offset + limit if offset + limit < len(filtered) else None,
    }


class FakeBackend:
    name = "fake"

    def __init__(self) -> None:
        self.timeline = Timeline()
        self.tracks: dict[str, dict[str, Any]] = {}
        self.transport: dict[str, Any] = {
            "samples": 0,
            "speed": 0.0,
            "record_enabled": False,
            "actively_recording": False,
            "loop": None,
        }
        self.snapshots: set[str] = set()
        self.connections: list[dict[str, Any]] = []
        self.counter = 0
        self.generation = 0
        self.undo_stack: list[dict[str, Any]] = []
        self.redo_stack: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._new_track("Master", "master", 2)

    def new_id(self, kind: str) -> str:
        self.counter += 1
        return f"fake-{kind}-{self.counter:08d}"

    @property
    def revision(self) -> str:
        # A content digest catches direct simulated human edits too.
        return "fake:" + fingerprint(
            {
                "tracks": self.tracks,
                "timeline": self.timeline.__dict__,
                "connections": self.connections,
                "snapshots": sorted(self.snapshots),
            }
        )

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(
            {
                "tracks": self.tracks,
                "timeline": self.timeline,
                "connections": self.connections,
                "snapshots": self.snapshots,
            }
        )

    def restore(self, state: dict[str, Any]) -> None:
        for key, value in state.items():
            setattr(self, key, copy.deepcopy(value))

    def track(self, a: dict[str, Any]) -> dict[str, Any]:
        track = self.tracks.get(a["track_id"])
        if track is None:
            raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Track ID not found.")
        return track

    def _new_track(self, name: str, kind: str, channels: int) -> dict[str, Any]:
        value: dict[str, Any] = {
            "id": self.new_id("route"),
            "name": name,
            "kind": kind,
            "channels": channels,
            "gain_db": 0.0,
            "pan": 0.0,
            "mute": False,
            "solo": False,
            "armed": False,
            "monitoring": "auto",
            "playlist_id": self.new_id("playlist") if kind in {"midi", "audio"} else None,
            "regions": {},
            "plugins": {},
            "sends": {},
            "automation": {},
        }
        self.tracks[value["id"]] = value
        return value

    def track_summary(self, value: dict[str, Any]) -> dict[str, Any]:
        return {
            k: v for k, v in value.items() if k not in {"regions", "plugins", "sends", "automation"}
        }

    async def execute(
        self, command: str, arguments: dict[str, JsonValue], options: Options
    ) -> Result:
        async with self._lock:
            spec = CATALOG.get(command)
            if spec is None:
                raise DomainError(ErrorCode.OPERATION_NOT_SUPPORTED, "Unknown simulator command.")
            before_rev = self.revision
            if options.expected_revision is not None and options.expected_revision != before_rev:
                raise DomainError(
                    ErrorCode.CONFLICT,
                    "Session revision changed.",
                    "Refresh state before retrying.",
                    current_revision=before_rev,
                )
            if spec.destructive and not options.confirm_delete and not options.dry_run:
                raise DomainError(ErrorCode.VALIDATION_ERROR, "Explicit confirm_delete required.")
            old = self.snapshot()
            old_transport = copy.deepcopy(self.transport)
            old_counter = self.counter
            old_undo, old_redo = copy.deepcopy(self.undo_stack), copy.deepcopy(self.redo_stack)
            try:
                data = self.dispatch(command, dict(arguments), options)
                changes = self.changes(old, self.snapshot()) if spec.mutates else []
                if options.dry_run:
                    self.restore(old)
                    self.transport = old_transport
                    self.counter = old_counter
                    self.undo_stack, self.redo_stack = old_undo, old_redo
                    return Result(
                        data={
                            "valid": True,
                            "expected_changes": [c.model_dump(mode="json") for c in changes],
                            "preview": data,
                        },
                        revision_before=before_rev,
                        revision_after=before_rev,
                    )
                if (
                    spec.mutates
                    and changes
                    and command not in {"undo", "redo", "save_session", "create_snapshot"}
                ):
                    self.undo_stack.append(old)
                    self.redo_stack.clear()
                return Result(
                    data=data,
                    revision_before=before_rev,
                    revision_after=self.revision,
                    changed_objects=changes,
                    warnings=["Simulated backend; no Ardour audio engine or plugin executes."],
                )
            except Exception:
                self.restore(old)
                self.transport = old_transport
                self.counter = old_counter
                self.undo_stack, self.redo_stack = old_undo, old_redo
                raise

    @staticmethod
    def changes(before: dict[str, Any], after: dict[str, Any]) -> list[Change]:
        result = []
        for object_id in sorted(set(before["tracks"]) | set(after["tracks"])):
            old, new = before["tracks"].get(object_id), after["tracks"].get(object_id)
            if old != new:
                # Bound dense-note payloads; inspect changed region with pagination for details.
                result.append(
                    Change(
                        object_id=object_id,
                        property="route_state",
                        before={"fingerprint": fingerprint(old)} if old else None,
                        after={"fingerprint": fingerprint(new)} if new else None,
                    )
                )
        if before["timeline"] != after["timeline"]:
            result.append(Change(object_id="fake-session", property="timeline"))
        if before["connections"] != after["connections"]:
            result.append(
                Change(
                    object_id="fake-session",
                    property="connections",
                    before=before["connections"],
                    after=after["connections"],
                )
            )
        return result

    def dispatch(self, command: str, a: dict[str, Any], options: Options) -> dict[str, Any]:
        if command in {"ping", "get_session_info"}:
            return {
                "session_id": "fake-session",
                "name": "Simulated Ardour",
                "sample_rate": self.timeline.sample_rate,
                "revision_scope": "complete simulated content",
                "simulated": True,
                "dirty": bool(self.undo_stack),
            }
        if command == "list_tracks":
            return paginate([self.track_summary(t) for t in self.tracks.values()], a)
        if command == "get_track":
            return self.track_summary(self.track(a))
        if command == "create_track":
            return self.track_summary(self._new_track(a["name"], a["kind"], a["channels"]))
        if command == "delete_track":
            t = self.track(a)
            if t["kind"] == "master":
                raise DomainError(ErrorCode.PERMISSION_DENIED, "Cannot delete master route.")
            del self.tracks[t["id"]]
            for other in self.tracks.values():
                other["sends"] = {
                    k: v for k, v in other["sends"].items() if v["target_id"] != t["id"]
                }
            return {"deleted_id": t["id"]}
        props = {
            "rename_track": ("name", "name"),
            "set_track_gain": ("gain_db", "gain_db"),
            "set_track_pan": ("pan", "pan"),
            "set_track_mute": ("mute", "enabled"),
            "set_track_solo": ("solo", "enabled"),
            "arm_track": ("armed", "enabled"),
            "set_monitoring": ("monitoring", "mode"),
        }
        if command in props:
            t = self.track(a)
            if command in {"arm_track", "set_monitoring"} and t["kind"] not in {"midi", "audio"}:
                raise DomainError(ErrorCode.OPERATION_NOT_SUPPORTED, "Route is not recordable.")
            prop, key = props[command]
            previous = t[prop]
            t[prop] = a[key]
            return {
                "object_id": t["id"],
                "property": prop,
                "before": previous,
                "after": t[prop],
                "undoable": True,
            }
        if command == "get_meter_state":
            return {"track_id": self.track(a)["id"], "peaks_dbfs": [None], "simulated": True}
        if command == "get_transport":
            return copy.deepcopy(self.transport)
        if command in {
            "play",
            "stop",
            "start_recording",
            "stop_recording",
            "locate",
            "set_loop",
            "clear_loop",
        }:
            if command == "locate":
                self.transport["samples"] = self.timeline.position(a["position"])
            elif command == "set_loop":
                start, end = self.timeline.position(a["start"]), self.timeline.position(a["end"])
                if end <= start:
                    raise DomainError(
                        ErrorCode.INVALID_TIME_POSITION, "Loop end must follow start."
                    )
                self.transport["loop"] = {"start_samples": start, "end_samples": end}
            elif command == "clear_loop":
                self.transport["loop"] = None
            else:
                if command == "start_recording" and not any(
                    t["armed"] for t in self.tracks.values()
                ):
                    raise DomainError(ErrorCode.VALIDATION_ERROR, "No tracks are armed.")
                self.transport["speed"] = 1.0 if command in {"play", "start_recording"} else 0.0
                if "recording" in command:
                    self.transport["record_enabled"] = command == "start_recording"
                    self.transport["actively_recording"] = command == "start_recording"
            return {"requested": command, **self.transport}
        if command == "convert_position":
            return self.timeline.convert(a["position"])
        if command in {"set_tempo", "set_time_signature"}:
            sample = self.timeline.position(a["position"])
            if command == "set_tempo":
                self.timeline.set_tempo(sample, a["bpm"])
            else:
                self.timeline.set_meter(sample, a["numerator"], a["denominator"])
            return {"tempos": self.timeline.tempos, "meters": self.timeline.meters}
        if command in {"save_session", "create_snapshot"}:
            if command == "create_snapshot":
                if a["name"] in self.snapshots:
                    raise DomainError(ErrorCode.FILE_EXISTS, "Snapshot exists.")
                self.snapshots.add(a["name"])
            return {"saved": True}
        if command in {"undo", "redo"}:
            source, target = (
                (self.undo_stack, self.redo_stack)
                if command == "undo"
                else (self.redo_stack, self.undo_stack)
            )
            if not source:
                raise DomainError(ErrorCode.OPERATION_NOT_SUPPORTED, "Undo/redo history is empty.")
            target.append(self.snapshot())
            self.restore(source.pop())
            return {"undo_count": len(self.undo_stack), "redo_count": len(self.redo_stack)}
        if command == "execute_batch":
            results = []
            for op in a["operations"]:
                if op["command"] not in COMPENSABLE:
                    raise DomainError(
                        ErrorCode.OPERATION_NOT_SUPPORTED,
                        "Batch includes a non-compensable command.",
                    )
                validated = CATALOG[op["command"]].request.model_validate(op["arguments"])
                results.append(
                    self.dispatch(op["command"], validated.model_dump(mode="json"), options)
                )
            return {
                "operations": results,
                "transaction_model": "simulated atomic snapshot",
                "name": a["name"],
            }
        result = plugin_command(self, command, a, options)
        if result is not None:
            return result
        result = edit_command(self, command, a, options)
        if result is not None:
            return result
        raise DomainError(
            ErrorCode.OPERATION_NOT_SUPPORTED, f"Simulator does not implement {command}."
        )

    async def capabilities(self) -> dict[str, JsonValue]:
        return {
            "backend": self.name,
            "simulated": True,
            "commands": [
                s.name for s in CATALOG.values() if not s.local and s.name != "render_range"
            ],
            "unsupported": UNSUPPORTED,
            "revision_scope": "complete simulated content",
            "audio_engine": False,
        }

    async def close(self) -> None:
        pass
