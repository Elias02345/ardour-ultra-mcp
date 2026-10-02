from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from ..models.base import DomainError, ErrorCode

if TYPE_CHECKING:
    from .fake import FakeBackend


def group_command(b: FakeBackend, command: str, a: dict[str, Any]) -> dict[str, Any] | None:
    from .fake import paginate

    if command == "list_groups":
        return paginate(list(b.groups.values()), a)
    if command == "create_group":
        if any(g["name"] == a["name"] for g in b.groups.values()):
            raise DomainError(ErrorCode.CONFLICT, "Group name already exists.")
        group = {
            "id": b.new_id("group"),
            "name": a["name"],
            "track_ids": [],
            "properties": {
                "active": True,
                "relative": True,
                "hidden": False,
                "gain": True,
                "mute": True,
                "solo": True,
                "recenable": True,
                "select": True,
                "color": True,
                "monitoring": True,
            },
            "undoable": False,
        }
        b.groups[group["id"]] = group
        return copy.deepcopy(group)
    if "group_id" not in a:
        return None
    g = b.groups.get(a["group_id"])
    if g is None:
        raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Route group ID not found.")
    if command == "delete_group":
        if not g["track_ids"]:
            raise DomainError(
                ErrorCode.OPERATION_NOT_SUPPORTED, "Native Ardour does not remove empty groups."
            )
        del b.groups[g["id"]]
        return {"deleted_id": g["id"], "preserved_track_ids": g["track_ids"], "undoable": False}
    if command == "set_group_properties":
        before = copy.deepcopy(g["properties"])
        g["properties"].update({k: v for k, v in a["properties"].items() if v is not None})
        return {
            "object_id": g["id"],
            "property": "group_properties",
            "before": before,
            "after": copy.deepcopy(g["properties"]),
            "undoable": False,
        }
    t = b.track(a)
    if command == "add_track_to_group":
        if t["kind"] == "master":
            raise DomainError(ErrorCode.PERMISSION_DENIED, "Singleton routes cannot join a group.")
        prior = next((x for x in b.groups.values() if t["id"] in x["track_ids"]), None)
        if prior and prior["id"] != g["id"]:
            raise DomainError(ErrorCode.CONFLICT, "Route already belongs to another group.")
        if prior is None:
            g["track_ids"].append(t["id"])
            g["track_ids"].sort()
        return {
            "group_id": g["id"],
            "track_id": t["id"],
            "already_member": prior is not None,
            "undoable": False,
        }
    if command == "remove_track_from_group":
        if t["id"] not in g["track_ids"]:
            raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Route is not a member of this group.")
        g["track_ids"].remove(t["id"])
        deleted = not g["track_ids"]
        if deleted:
            del b.groups[g["id"]]
        return {
            "group_id": g["id"],
            "removed_track_id": t["id"],
            "group_deleted": deleted,
            "undoable": False,
        }
    return None
