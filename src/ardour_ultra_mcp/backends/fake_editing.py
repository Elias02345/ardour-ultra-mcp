from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from ..models.base import DomainError, ErrorCode, Options

if TYPE_CHECKING:
    from .fake import FakeBackend


def edit_command(
    b: FakeBackend, command: str, a: dict[str, Any], options: Options
) -> dict[str, Any] | None:
    from .fake import fingerprint, paginate

    if command == "list_regions":
        return paginate(
            [
                {k: v for k, v in r.items() if k != "notes"}
                for r in b.track(a)["regions"].values()
                if a["kind"] in {"all", r["kind"]}
            ],
            a,
        )
    if command == "create_midi_region":
        t = b.track(a)
        if t["kind"] != "midi":
            raise DomainError(ErrorCode.OPERATION_NOT_SUPPORTED, "MIDI region requires MIDI track.")
        start, end = b.timeline.position(a["start"]), b.timeline.position(a["end"])
        if end <= start:
            raise DomainError(ErrorCode.INVALID_TIME_POSITION, "Region end must follow start.")
        r = {
            "id": b.new_id("region"),
            "name": a["name"],
            "kind": "midi",
            "track_id": t["id"],
            "playlist_id": t["playlist_id"],
            "position_samples": start,
            "length_samples": end - start,
            "source_start_ticks": 0,
            "source_start_samples": 0,
            "muted": False,
            "locked": False,
            "notes": [],
        }
        t["regions"][r["id"]] = r
        return {k: v for k, v in r.items() if k != "notes"}
    if "region_id" in a:
        regions = b.track(a)["regions"]
        r = regions.get(a["region_id"])
        if r is None:
            raise DomainError(
                ErrorCode.OBJECT_NOT_FOUND, "Region not in specified track's active playlist."
            )
        if command == "get_region":
            return {k: copy.deepcopy(v) for k, v in r.items() if k != "notes"}
        if r["locked"] and command not in {"get_region", "list_midi_notes", "set_region_lock"}:
            raise DomainError(ErrorCode.PERMISSION_DENIED, "Region is locked.")
        if command == "move_region":
            r["position_samples"] = b.timeline.position(a["position"])
            return {"region_id": r["id"], "position_samples": r["position_samples"]}
        if command == "trim_region":
            start, end = b.timeline.position(a["start"]), b.timeline.position(a["end"])
            old_start = r["position_samples"]
            if start < old_start or end > old_start + r["length_samples"] or end <= start:
                raise DomainError(
                    ErrorCode.INVALID_TIME_POSITION, "Trim bounds must lie within original region."
                )
            r["source_start_samples"] += start - old_start
            r["source_start_ticks"] += b.timeline.samples_to_ticks(
                start
            ) - b.timeline.samples_to_ticks(old_start)
            r["position_samples"], r["length_samples"] = start, end - start
            return {"region_id": r["id"], "position_samples": start, "length_samples": end - start}
        if command == "split_region":
            split = b.timeline.position(a["position"])
            start, end = r["position_samples"], r["position_samples"] + r["length_samples"]
            if not start < split < end:
                raise DomainError(
                    ErrorCode.INVALID_TIME_POSITION, "Split must lie strictly inside region."
                )
            left, right = copy.deepcopy(r), copy.deepcopy(r)
            left["id"], right["id"] = b.new_id("region"), b.new_id("region")
            left["length_samples"] = split - start
            right["position_samples"], right["length_samples"] = split, end - split
            right["source_start_samples"] += split - start
            right["source_start_ticks"] += b.timeline.samples_to_ticks(
                split
            ) - b.timeline.samples_to_ticks(start)
            del regions[r["id"]]
            regions[left["id"]], regions[right["id"]] = left, right
            return {"removed_id": r["id"], "region_ids": [left["id"], right["id"]]}
        if command == "delete_region":
            del regions[r["id"]]
            return {"deleted_id": r["id"]}
        if command in {"set_region_lock", "set_region_mute", "set_region_gain", "set_region_fades"}:
            if command in {"set_region_gain", "set_region_fades"} and r["kind"] != "audio":
                raise DomainError(ErrorCode.OPERATION_NOT_SUPPORTED, "Requires audio region.")
            if command == "set_region_gain":
                r["gain_db"] = a["gain_db"]
            elif command == "set_region_lock":
                r["locked"] = a["enabled"]
            elif command == "set_region_mute":
                r["muted"] = a["enabled"]
            else:
                if max(a["fade_in_samples"], a["fade_out_samples"]) > r["length_samples"]:
                    raise DomainError(ErrorCode.VALIDATION_ERROR, "Fade exceeds region length.")
                r["fade_in_samples"], r["fade_out_samples"] = (
                    a["fade_in_samples"],
                    a["fade_out_samples"],
                )
            return {"region_id": r["id"], "undoable": True}
        if command in {
            "list_midi_notes",
            "insert_midi_notes",
            "edit_midi_notes",
            "delete_midi_notes",
        }:
            if r["kind"] != "midi":
                raise DomainError(ErrorCode.OPERATION_NOT_SUPPORTED, "Requires MIDI region.")
            notes = r["notes"]
            digest = fingerprint(notes)
            if command == "list_midi_notes":
                values = [{**n, "note_ref": f"{digest}:{i}"} for i, n in enumerate(notes)]
                return {
                    **paginate(values, a),
                    "model_fingerprint": digest,
                    "ticks_per_quarter": 1920,
                    "scope": "source-relative; notes may lie outside trimmed region",
                }
            if command == "insert_midi_notes":
                notes.extend(copy.deepcopy(a["notes"]))
            else:
                if a["model_fingerprint"] != digest:
                    raise DomainError(
                        ErrorCode.STALE_OBJECT,
                        "MIDI model changed since note references were read.",
                    )
                values = a["replacements"] if command == "edit_midi_notes" else a["note_refs"]
                changes = {}
                for value in values:
                    ref = value["note_ref"] if isinstance(value, dict) else value
                    prefix, _, index = ref.rpartition(":")
                    if (
                        prefix != digest
                        or not index.isdecimal()
                        or not 0 <= int(index) < len(notes)
                        or int(index) in changes
                    ):
                        raise DomainError(
                            ErrorCode.STALE_OBJECT, "Invalid or duplicate guarded note reference."
                        )
                    changes[int(index)] = value["note"] if isinstance(value, dict) else None
                r["notes"] = [
                    changes.get(i, n)
                    for i, n in enumerate(notes)
                    if i not in changes or changes[i] is not None
                ]
            return {
                "region_id": r["id"],
                "note_count": len(r["notes"]),
                "model_fingerprint": fingerprint(r["notes"]),
                "undoable": True,
            }
    if command in {
        "get_automation",
        "create_automation_points",
        "clear_automation",
        "set_automation_mode",
    }:
        t = b.track(a)
        target = f"{a['control']}:{a.get('processor_id')}:{a.get('parameter_index')}"
        unit = {
            "gain": "linear_gain",
            "send": "linear_gain",
            "pan": "normalized_azimuth",
            "plugin": "plugin_native",
        }[a["control"]]
        low, high = (0.0, 2.0) if a["control"] in {"gain", "send"} else (0.0, 1.0)
        if a["control"] == "plugin":
            p = t["plugins"].get(a["processor_id"])
            if p is None:
                raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Plugin not on track.")
            if a["parameter_index"] >= len(p["parameters"]):
                raise DomainError(ErrorCode.PARAMETER_NOT_FOUND, "Parameter missing.")
            param = p["parameters"][a["parameter_index"]]
            low, high = param["minimum"], param["maximum"]
        if a["control"] == "send" and a["processor_id"] not in t["sends"]:
            raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Send not on track.")
        current: dict[str, Any] = copy.deepcopy(
            t["automation"].get(
                target, {"points": [], "mode": "off", "unit": unit, "interpolation": "linear"}
            )
        )
        if command == "get_automation":
            return current
        if command == "set_automation_mode":
            current["mode"] = a["mode"]
        elif command == "clear_automation":
            current["points"] = []
        else:
            if a["unit"] != unit:
                raise DomainError(ErrorCode.VALIDATION_ERROR, "Automation unit mismatch.")
            if a["replace"] and not options.confirm_delete and not options.dry_run:
                raise DomainError(ErrorCode.VALIDATION_ERROR, "Replace requires confirm_delete.")
            points = [
                {"samples": b.timeline.position(p["position"]), "value": p["value"]}
                for p in a["points"]
            ]
            if any(not low <= p["value"] <= high for p in points):
                raise DomainError(
                    ErrorCode.VALIDATION_ERROR, "Automation value outside control range."
                )
            if len({p["samples"] for p in points}) != len(points):
                raise DomainError(ErrorCode.VALIDATION_ERROR, "Duplicate point positions.")
            merged = {p["samples"]: p for p in ([] if a["replace"] else current["points"])}
            merged.update({p["samples"]: p for p in points})
            current["points"] = [merged[k] for k in sorted(merged)]
            current["interpolation"] = a["interpolation"]
        t["automation"][target] = current
        return {**current, "undoable": command != "set_automation_mode"}
    return None
