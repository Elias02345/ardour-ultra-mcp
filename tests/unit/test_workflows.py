import copy

from ardour_ultra_mcp.models.base import ErrorCode


async def test_ensure_bus_preflight_idempotency_and_conflicts(service, backend):
    before = (backend.revision, backend.counter, copy.deepcopy(backend.undo_stack))
    dry = await service.call("ensure_bus", {"name": "Verb", "dry_run": True})
    assert dry.success and not dry.data["created"]
    assert before == (backend.revision, backend.counter, backend.undo_stack)
    first = await service.call("ensure_bus", {"name": "Verb"})
    assert first.success and first.data["created"] and first.changed_objects
    second = await service.call("ensure_bus", {"name": "Verb"})
    assert second.success and not second.data["created"] and not second.changed_objects
    assert second.data["bus"]["id"] == first.data["bus"]["id"]
    assert (
        await service.call("ensure_bus", {"name": "Verb", "channels": 1})
    ).error.code == ErrorCode.CONFLICT
    await service.call("create_track", {"name": "Verb", "kind": "audio"})
    assert (await service.call("ensure_bus", {"name": "Verb"})).error.code == ErrorCode.CONFLICT
    assert (
        await service.call("ensure_bus", {"name": "New", "expected_revision": first.revision_after})
    ).error.code == ErrorCode.CONFLICT


async def test_ensure_bus_enumerates_full_filter_pages(service, backend):
    for i in range(1001):
        backend._new_track(f"Verb variant {i}", "bus", 2)
    actual = backend._new_track("Verb", "bus", 2)
    found = await service.call("ensure_bus", {"name": "Verb"})
    assert found.success and not found.data["created"] and found.data["bus"]["id"] == actual["id"]


async def test_midi_nondefault_channel_width_not_silently_ignored(service):
    result = await service.call(
        "create_track", {"name": "Wrong width", "kind": "midi", "channels": 1}
    )
    assert result.error.code == ErrorCode.VALIDATION_ERROR
