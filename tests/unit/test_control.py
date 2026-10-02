import copy
import json

import pytest

from ardour_ultra_mcp.models.base import ErrorCode


async def test_precision_and_stable_identity(service, backend):
    one = await service.call("create_track", {"name": "Bass", "kind": "midi"})
    two = await service.call("create_track", {"name": "Bass", "kind": "audio"})
    identity = one.data["id"]
    assert identity != two.data["id"]
    gain = await service.call(
        "set_track_gain",
        {"track_id": identity, "gain_db": -4.25, "expected_revision": one.revision_after},
    )
    assert not gain.success and gain.error.code == ErrorCode.CONFLICT
    gain = await service.call("set_track_gain", {"track_id": identity, "gain_db": -4.25})
    assert gain.success and gain.revision_before != gain.revision_after and gain.changed_objects
    pan = await service.call("set_track_pan", {"track_id": identity, "pan": -0.35})
    assert pan.success
    inspected = await service.call("get_track", {"track_id": identity})
    assert inspected.data["gain_db"] == -4.25 and inspected.data["pan"] == -0.35
    backend.tracks = dict(reversed(list(backend.tracks.items())))
    assert (await service.call("get_track", {"track_id": identity})).data["gain_db"] == -4.25
    assert (await service.call("get_track", {"track_id": two.data["id"]})).data["gain_db"] == 0


@pytest.mark.parametrize("value", [7, -194, float("nan"), float("inf"), None, "louder"])
async def test_gain_validation_no_mutation(service, midi, backend, value):
    before = backend.revision
    result = await service.call("set_track_gain", {"track_id": midi["track_id"], "gain_db": value})
    assert not result.success and result.error.code == ErrorCode.VALIDATION_ERROR
    assert backend.revision == before


@pytest.mark.parametrize("name", ["../evil", "a/b", "x\\y", "\x00bad", "", "x" * 201])
async def test_name_validation(service, backend, name):
    before = backend.revision
    result = await service.call("create_track", {"name": name, "kind": "audio"})
    assert not result.success and backend.revision == before


async def test_delete_preflight_and_singletons(service, midi, backend):
    before = backend.revision
    result = await service.call("delete_track", midi)
    assert not result.success
    request = {"track_id": midi["track_id"]}
    dry = await service.call("delete_track", {**request, "dry_run": True})
    assert dry.success and dry.data["valid"] and backend.revision == before
    denied = await service.call("delete_track", request)
    assert denied.error.code == ErrorCode.VALIDATION_ERROR
    deleted = await service.call("delete_track", {**request, "confirm_delete": True})
    assert deleted.success
    missing = await service.call("get_track", request)
    assert missing.error.code == ErrorCode.OBJECT_NOT_FOUND
    master = next(t for t in backend.tracks.values() if t["kind"] == "master")
    assert not (
        await service.call("delete_track", {"track_id": master["id"], "confirm_delete": True})
    ).success


async def test_dry_run_does_not_consume_ids_or_undo(service, backend):
    before = (backend.revision, backend.counter, copy.deepcopy(backend.undo_stack))
    result = await service.call("create_track", {"name": "Preview", "kind": "bus", "dry_run": True})
    assert result.success and result.data["valid"]
    assert before == (backend.revision, backend.counter, backend.undo_stack)


async def test_compensable_batch_rolls_back_invalid_second_operation(service, midi, backend):
    before = backend.revision
    result = await service.call(
        "execute_batch",
        {
            "operations": [
                {
                    "command": "set_track_gain",
                    "arguments": {"track_id": midi["track_id"], "gain_db": -6},
                },
                {"command": "rename_track", "arguments": {"track_id": "missing", "name": "New"}},
            ]
        },
    )
    assert not result.success and result.error.code == ErrorCode.OBJECT_NOT_FOUND
    assert backend.revision == before
    assert (await service.call("get_track", {"track_id": midi["track_id"]})).data["gain_db"] == 0


async def test_batch_rejects_nested_options_and_noncompensable(service, midi):
    for operation in [
        {
            "command": "delete_track",
            "arguments": {"track_id": midi["track_id"], "confirm_delete": True},
        },
        {
            "command": "set_track_gain",
            "arguments": {"track_id": midi["track_id"], "gain_db": -1, "dry_run": True},
        },
    ]:
        assert not (await service.call("execute_batch", {"operations": [operation]})).success


async def test_exact_plugin_values_and_atomic_validation(service, plugin):
    result = await service.call(
        "set_plugin_parameters",
        {
            **plugin,
            "parameters": [{"parameter_index": 0, "value": 1834.5, "unit": "plugin_native"}],
        },
    )
    assert result.success and result.data["parameters"][0]["after"] == 1834.5
    bad = await service.call(
        "set_plugin_parameters",
        {
            **plugin,
            "parameters": [
                {"parameter_index": 0, "value": 700},
                {"parameter_index": 1, "value": 99},
            ],
        },
    )
    assert not bad.success
    values = await service.call("get_plugin_parameters", plugin)
    assert values.data["items"][0]["value"] == 1834.5
    assert not (
        await service.call(
            "set_plugin_parameters",
            {**plugin, "parameters": [{"parameter_index": 0, "value": 1000, "unit": "Hz"}]},
        )
    ).success
    assert not (
        await service.call(
            "set_plugin_parameters", {**plugin, "parameters": [{"parameter_index": 77, "value": 1}]}
        )
    ).success


async def test_inventory_pagination_and_no_arbitrary_dispatch(service):
    inventory = await service.call("list_available_plugins", {"limit": 1})
    assert (
        inventory.success
        and len(inventory.data["items"]) == 1
        and inventory.data["next_offset"] == 1
    )
    filtered = await service.call("list_available_plugins", {"name_filter": "eq"})
    assert filtered.data["total"] == 1
    for command in ["execute_arbitrary_lua", "run_shell", "import_audio"]:
        result = await service.call(command, {})
        assert not result.success and result.error.code == ErrorCode.OPERATION_NOT_SUPPORTED
    json.dumps(inventory.model_dump(mode="json"), allow_nan=False)


async def test_transport_record_and_dryrun(service, midi):
    assert not (await service.call("start_recording", {})).success
    assert (
        await service.call("arm_track", {"track_id": midi["track_id"], "enabled": True})
    ).success
    assert (await service.call("start_recording", {"dry_run": True})).success
    assert not (await service.call("get_transport", {})).data["actively_recording"]
    assert (await service.call("start_recording", {})).success
    assert (await service.call("get_transport", {})).data["actively_recording"]
    assert (await service.call("stop_recording", {})).success
    assert not (await service.call("get_transport", {})).data["actively_recording"]
