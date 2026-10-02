from ardour_ultra_mcp.models.base import ErrorCode


async def test_group_membership_identity_and_safety(service, backend, midi):
    group = await service.call("create_group", {"name": "Drums"})
    gid = group.data["id"]
    ref = {"group_id": gid, "track_id": midi["track_id"]}
    assert (await service.call("add_track_to_group", ref)).success
    assert (await service.call("add_track_to_group", ref)).data["already_member"]
    another = await service.call("create_group", {"name": "Other"})
    refused = await service.call("add_track_to_group", {**ref, "group_id": another.data["id"]})
    assert refused.error.code == ErrorCode.CONFLICT
    master = next(t for t in backend.tracks.values() if t["kind"] == "master")
    refused = await service.call("add_track_to_group", {"group_id": gid, "track_id": master["id"]})
    assert refused.error.code == ErrorCode.PERMISSION_DENIED
    assert (await service.call("create_group", {"name": "Drums"})).error.code == ErrorCode.CONFLICT
    assert not (await service.call("delete_group", {"group_id": gid})).success
    before = backend.revision
    assert (await service.call("delete_group", {"group_id": gid, "dry_run": True})).success
    assert backend.revision == before
    assert (await service.call("remove_track_from_group", ref)).success
    assert (
        await service.call("remove_track_from_group", ref)
    ).error.code == ErrorCode.OBJECT_NOT_FOUND
    recreated = await service.call("create_group", {"name": "Drums"})
    gid = recreated.data["id"]
    assert (
        await service.call("delete_group", {"group_id": gid, "confirm_delete": True})
    ).error.code == ErrorCode.OPERATION_NOT_SUPPORTED
    ref["group_id"] = gid
    assert (await service.call("add_track_to_group", ref)).success
    result = await service.call("delete_group", {"group_id": gid, "confirm_delete": True})
    assert result.success and result.data["preserved_track_ids"] == [midi["track_id"]]
    assert (await service.call("get_track", {"track_id": midi["track_id"]})).success


async def test_group_revision_partial_properties_and_delete_cleanup(service, backend, midi):
    group = await service.call("create_group", {"name": "Linked"})
    ref = {"group_id": group.data["id"]}
    for properties in [{}, {"gain": None}, {"gain": "sometimes"}, {"unknown": True}]:
        before = backend.revision
        assert not (
            await service.call("set_group_properties", {**ref, "properties": properties})
        ).success
        assert backend.revision == before
    changed = await service.call("set_group_properties", {**ref, "properties": {"gain": False}})
    assert changed.success and changed.changed_objects
    assert changed.data["before"]["gain"] is True and changed.data["after"]["gain"] is False
    assert changed.data["after"]["solo"] is True
    stale = await service.call(
        "add_track_to_group",
        {**ref, "track_id": midi["track_id"], "expected_revision": group.revision_after},
    )
    assert stale.error.code == ErrorCode.CONFLICT
    assert (await service.call("add_track_to_group", {**ref, "track_id": midi["track_id"]})).success
    assert (
        await service.call("delete_track", {"track_id": midi["track_id"], "confirm_delete": True})
    ).success
    assert (await service.call("list_groups", {})).data["total"] == 0


async def test_copy_region_independent_source_and_undo(service, midi):
    note = {"pitch": 60, "velocity": 104, "start_ticks": 0, "duration_ticks": 480}
    await service.call("insert_midi_notes", {**midi, "notes": [note]})
    dest = await service.call("create_track", {"name": "Copy", "kind": "midi"})
    request = {
        **midi,
        "target_track_id": dest.data["id"],
        "name": "Copy pattern",
        "position": {"unit": "bbt", "bar": 10, "beat": 1},
    }
    preview = await service.call("copy_region", {**request, "dry_run": True})
    assert preview.success
    assert (await service.call("list_regions", {"track_id": dest.data["id"]})).data["total"] == 0
    copy = await service.call("copy_region", request)
    ref = {"track_id": dest.data["id"], "region_id": copy.data["id"]}
    assert copy.success and copy.data["independent_midi_source"]
    await service.call("undo", {})
    assert (await service.call("get_region", ref)).error.code == ErrorCode.OBJECT_NOT_FOUND
    await service.call("redo", {})
    await service.call("insert_midi_notes", {**ref, "notes": [{**note, "pitch": 37}]})
    assert (await service.call("list_midi_notes", midi)).data["total"] == 1
    assert (await service.call("list_midi_notes", ref)).data["total"] == 2
    assert (await service.call("list_regions", {"track_id": dest.data["id"]})).data["items"][0][
        "playlist_id"
    ] == dest.data["playlist_id"]
    incompatible = await service.call("create_track", {"name": "Audio", "kind": "audio"})
    assert (
        await service.call("copy_region", {**request, "target_track_id": incompatible.data["id"]})
    ).error.code == ErrorCode.OPERATION_NOT_SUPPORTED
