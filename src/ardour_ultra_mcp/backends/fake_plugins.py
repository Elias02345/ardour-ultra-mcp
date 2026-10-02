from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from ..models.base import DomainError, ErrorCode, Options

if TYPE_CHECKING:
    from .fake import FakeBackend

INVENTORY = [
    {
        "plugin_id": "urn:ultra:simulated:filter",
        "name": "Simulated Filter",
        "format": "LV2",
        "category": "EQ",
        "is_instrument": False,
        "simulated": True,
    },
    {
        "plugin_id": "urn:ultra:simulated:synth",
        "name": "Simulated Synth",
        "format": "LV2",
        "category": "Instrument",
        "is_instrument": True,
        "simulated": True,
    },
]


def plugin_command(
    b: FakeBackend, command: str, a: dict[str, Any], options: Options
) -> dict[str, Any] | None:
    from .fake import paginate

    if command == "list_available_plugins":
        return paginate(INVENTORY, a)
    if command == "list_track_plugins":
        return paginate(list(b.track(a)["plugins"].values()), a)
    if command == "add_plugin":
        matches = [
            p for p in INVENTORY if p["plugin_id"] == a["plugin_id"] and p["format"] == a["format"]
        ]
        if not matches:
            raise DomainError(ErrorCode.PLUGIN_NOT_FOUND, "Simulator plugin not in inventory.")
        t = b.track(a)
        p = {
            **matches[0],
            "id": b.new_id("processor"),
            "enabled": True,
            "index": a["index"],
            "parameters": [
                {
                    "parameter_index": 0,
                    "parameter_id": "0",
                    "name": "Cutoff",
                    "value": 1000.0,
                    "minimum": 20.0,
                    "maximum": 20000.0,
                    "default": 1000.0,
                    "unit": "plugin_native",
                    "display_format": "%.1f Hz",
                    "automation_capable": True,
                },
                {
                    "parameter_index": 1,
                    "parameter_id": "1",
                    "name": "Gain",
                    "value": 0.0,
                    "minimum": -24.0,
                    "maximum": 24.0,
                    "default": 0.0,
                    "unit": "plugin_native",
                    "display_format": "%.1f dB",
                    "automation_capable": True,
                },
            ],
            "presets": [{"label": "Default", "uri": "urn:default", "user": False}],
        }
        t["plugins"][p["id"]] = p
        return {"processor_id": p["id"], "plugin_id": p["plugin_id"]}
    if "processor_id" in a and command in {
        "remove_plugin",
        "set_plugin_enabled",
        "get_plugin_parameters",
        "set_plugin_parameters",
        "list_plugin_presets",
        "load_plugin_preset",
    }:
        t = b.track(a)
        p = t["plugins"].get(a["processor_id"])
        if p is None:
            raise DomainError(
                ErrorCode.OBJECT_NOT_FOUND, "Plugin processor not on specified track."
            )
        if command == "remove_plugin":
            del t["plugins"][p["id"]]
            return {"deleted_id": p["id"]}
        if command == "set_plugin_enabled":
            p["enabled"] = a["enabled"]
            return {"enabled": p["enabled"]}
        if command == "get_plugin_parameters":
            return paginate(p["parameters"], a)
        if command == "list_plugin_presets":
            return {"items": p["presets"]}
        if command == "load_plugin_preset":
            if a["label"] != "Default":
                raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Preset not found.")
            for value in p["parameters"]:
                value["value"] = value["default"]
            return {"loaded": a["label"]}
        indices = set()
        changes = []
        for item in a["parameters"]:
            index = item["parameter_index"]
            if index >= len(p["parameters"]):
                raise DomainError(ErrorCode.PARAMETER_NOT_FOUND, "Parameter ordinal out of range.")
            if index in indices:
                raise DomainError(ErrorCode.VALIDATION_ERROR, "Duplicate parameter index.")
            indices.add(index)
            param = p["parameters"][index]
            if (
                item["unit"] != param["unit"]
                or not param["minimum"] <= item["value"] <= param["maximum"]
            ):
                raise DomainError(ErrorCode.VALIDATION_ERROR, "Parameter unit/range mismatch.")
            changes.append(
                {"parameter_index": index, "before": param["value"], "after": item["value"]}
            )
        for change in changes:
            p["parameters"][change["parameter_index"]]["value"] = change["after"]
        return {"processor_id": p["id"], "parameters": changes}
    if command == "list_sends":
        return paginate(list(b.track(a)["sends"].values()), a)
    if command == "create_send":
        t = b.track(a)
        target = b.tracks.get(a["target_id"])
        if target is None:
            raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Send destination not found.")
        if target["kind"] not in {"bus", "master"}:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Send destination must be a bus.")
        visited = set()

        def reaches(route_id: str) -> bool:
            if route_id == t["id"]:
                return True
            if route_id in visited:
                return False
            visited.add(route_id)
            return any(reaches(s["target_id"]) for s in b.tracks[route_id]["sends"].values())

        if reaches(target["id"]):
            raise DomainError(ErrorCode.PERMISSION_DENIED, "Send would create feedback cycle.")
        s = {
            "id": b.new_id("send"),
            "name": target["name"],
            "target_id": target["id"],
            "gain_db": a["gain_db"],
        }
        t["sends"][s["id"]] = s
        return copy.deepcopy(s)
    if command in {"set_send_gain", "remove_send"}:
        t = b.track(a)
        s = t["sends"].get(a["send_id"])
        if s is None:
            raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Send not on track.")
        if command == "remove_send":
            del t["sends"][s["id"]]
            return {"deleted_id": s["id"]}
        previous = s["gain_db"]
        s["gain_db"] = a["gain_db"]
        return {"before": previous, "after": s["gain_db"]}
    if command == "list_ports":
        ports = [
            {"name": f"{t['id']}/{direction} {i + 1}", "direction": direction, "data_type": "audio"}
            for t in b.tracks.values()
            for direction in ["in", "out"]
            for i in range(t["channels"])
        ]
        return paginate(ports, a)
    if command in {"connect_ports", "disconnect_ports"}:
        connection = {"source": a["source"], "destination": a["destination"]}
        valid = plugin_command(b, "list_ports", {"limit": 100000}, options)
        if valid is None:
            raise DomainError(ErrorCode.BACKEND_ERROR, "Simulator port inventory unavailable.")
        port_map = {v["name"]: v for v in valid["items"]}
        if a["source"] not in port_map or a["destination"] not in port_map:
            raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Port not found.")
        if (
            port_map[a["source"]]["direction"] != "out"
            or port_map[a["destination"]]["direction"] != "in"
        ):
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Expected output to input connection.")
        if command == "connect_ports":
            if connection not in b.connections:
                b.connections.append(connection)
        elif connection in b.connections:
            b.connections.remove(connection)
        return {"connections": copy.deepcopy(b.connections)}
    return None
