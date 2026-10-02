from ardour_ultra_mcp.models.base import ErrorCode


async def test_bus_sends_and_feedback_rejection(service, midi):
    bus = await service.call("create_track", {"name": "Verb", "kind": "bus"})
    other = await service.call("create_track", {"name": "Delay", "kind": "bus"})
    send = await service.call(
        "create_send", {"track_id": midi["track_id"], "target_id": bus.data["id"], "gain_db": -6}
    )
    assert send.success and send.data["gain_db"] == -6
    assert (
        await service.call(
            "set_send_gain",
            {"track_id": midi["track_id"], "send_id": send.data["id"], "gain_db": -4.25},
        )
    ).success
    sends = await service.call("list_sends", {"track_id": midi["track_id"]})
    assert sends.data["items"][0]["gain_db"] == -4.25
    assert (
        await service.call(
            "create_send", {"track_id": bus.data["id"], "target_id": other.data["id"]}
        )
    ).success
    cycle = await service.call(
        "create_send", {"track_id": other.data["id"], "target_id": bus.data["id"]}
    )
    assert not cycle.success and cycle.error.code == ErrorCode.PERMISSION_DENIED


async def test_automation_curve_preflight_undo_and_replacement(service, midi):
    target = {"track_id": midi["track_id"], "control": "gain"}
    points = [
        {"position": {"unit": "samples", "samples": i * 480}, "value": i / 100} for i in range(101)
    ]
    dry = await service.call(
        "create_automation_points",
        {**target, "points": points, "unit": "linear_gain", "dry_run": True},
    )
    assert dry.success and (await service.call("get_automation", target)).data["points"] == []
    made = await service.call(
        "create_automation_points", {**target, "points": points, "unit": "linear_gain"}
    )
    assert made.success and made.data["points"][37] == {"samples": 17760, "value": 0.37}
    denied = await service.call(
        "create_automation_points",
        {**target, "points": points[:1], "unit": "linear_gain", "replace": True},
    )
    assert not denied.success
    cleared = await service.call("clear_automation", {**target, "confirm_delete": True})
    assert cleared.success and cleared.data["points"] == []
    assert (await service.call("undo", {})).success
    assert len((await service.call("get_automation", target)).data["points"]) == 101
    invalid = await service.call(
        "create_automation_points", {**target, "points": points[:2], "unit": "normalized_azimuth"}
    )
    assert not invalid.success


async def test_plugin_automation_units(service, plugin):
    target = {**plugin, "control": "plugin", "parameter_index": 0}
    curve = await service.call(
        "create_automation_points",
        {
            **target,
            "unit": "plugin_native",
            "points": [
                {"position": {"unit": "bbt", "bar": 4, "beat": 1}, "value": 700},
                {"position": {"unit": "bbt", "bar": 8, "beat": 1}, "value": 2400},
            ],
        },
    )
    assert curve.success and curve.data["anchor_at_zero_added"]
    assert curve.data["points"] == [
        {"samples": 0, "value": 700},
        {"samples": 288000, "value": 700},
        {"samples": 672000, "value": 2400},
    ]
    assert (await service.call("set_automation_mode", {**target, "mode": "play"})).success
    assert (await service.call("get_automation", target)).data["mode"] == "play"


async def test_automation_anchor_limit_upsert_and_rollback(service, midi):
    target = {"track_id": midi["track_id"], "control": "gain", "unit": "linear_gain"}
    points = [
        {"position": {"unit": "samples", "samples": i + 1}, "value": 0.5} for i in range(10000)
    ]
    denied = await service.call("create_automation_points", {**target, "points": points})
    assert not denied.success and denied.error.code == ErrorCode.BACKEND_UNSUPPORTED
    assert (
        await service.call("get_automation", {"track_id": midi["track_id"], "control": "gain"})
    ).data["points"] == []
    made = await service.call("create_automation_points", {**target, "points": points[:-1]})
    assert made.success and len(made.data["points"]) == 10000
    updated = await service.call(
        "create_automation_points",
        {**target, "points": [{"position": {"unit": "samples", "samples": 400}, "value": 0.75}]},
    )
    assert updated.success and len(updated.data["points"]) == 10000
    assert updated.data["points"][400] == {"samples": 400, "value": 0.75}
    assert (await service.call("undo", {})).success
    curve = await service.call("get_automation", {"track_id": midi["track_id"], "control": "gain"})
    assert curve.data["points"][400]["value"] == 0.5
