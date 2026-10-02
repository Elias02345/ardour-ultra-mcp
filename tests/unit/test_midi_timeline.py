import pytest

from ardour_ultra_mcp.models.base import DomainError, ErrorCode
from ardour_ultra_mcp.state.timeline import Timeline

NOTE = {"pitch": 48, "velocity": 108, "channel": 1, "start_ticks": 0, "duration_ticks": 240}


async def test_dense_notes_guarded_references_and_native_undo(service, midi):
    notes = [
        {**NOTE, "start_ticks": i * 240, "velocity": 94 if i % 2 else 108} for i in range(10000)
    ]
    result = await service.call("insert_midi_notes", {**midi, "notes": notes})
    assert result.success and result.data["note_count"] == 10000
    first = await service.call("list_midi_notes", {**midi, "limit": 2})
    assert first.data["total"] == 10000 and len(first.data["items"]) == 2
    n = first.data["items"][1]
    assert n["start_ticks"] == 240 and n["velocity"] == 94
    edited = await service.call(
        "edit_midi_notes",
        {
            **midi,
            "model_fingerprint": first.data["model_fingerprint"],
            "replacements": [
                {"note_ref": n["note_ref"], "note": {**NOTE, "pitch": 60, "start_ticks": 240}}
            ],
        },
    )
    assert edited.success
    stale = await service.call(
        "delete_midi_notes",
        {
            **midi,
            "model_fingerprint": first.data["model_fingerprint"],
            "note_refs": [n["note_ref"]],
            "confirm_delete": True,
        },
    )
    assert not stale.success and stale.error.code == ErrorCode.STALE_OBJECT
    assert (await service.call("undo", {})).success
    restored = await service.call("list_midi_notes", {**midi, "offset": 1, "limit": 1})
    assert restored.data["items"][0]["pitch"] == 48
    assert (await service.call("redo", {})).success
    assert (await service.call("list_midi_notes", {**midi, "offset": 1, "limit": 1})).data["items"][
        0
    ]["pitch"] == 60


async def test_references_reject_duplicate_and_human_edit(service, midi, backend):
    await service.call("insert_midi_notes", {**midi, "notes": [NOTE, NOTE]})
    result = await service.call("list_midi_notes", midi)
    note = result.data["items"][0]
    duplicate = await service.call(
        "delete_midi_notes",
        {
            **midi,
            "model_fingerprint": result.data["model_fingerprint"],
            "note_refs": [note["note_ref"], note["note_ref"]],
            "confirm_delete": True,
        },
    )
    assert not duplicate.success
    backend.tracks[midi["track_id"]]["regions"][midi["region_id"]]["notes"][0]["velocity"] = 107
    changed = await service.call(
        "edit_midi_notes",
        {
            **midi,
            "model_fingerprint": result.data["model_fingerprint"],
            "replacements": [{"note_ref": note["note_ref"], "note": NOTE}],
        },
    )
    assert changed.error.code == ErrorCode.STALE_OBJECT


@pytest.mark.parametrize(
    "changes",
    [
        {"pitch": 128},
        {"velocity": 0},
        {"channel": 0},
        {"channel": 17},
        {"duration_ticks": 0},
        {"start_ticks": -1},
        {"start_ticks": 1.5},
        {"pitch": True},
    ],
)
async def test_note_boundaries(service, midi, changes):
    result = await service.call("insert_midi_notes", {**midi, "notes": [{**NOTE, **changes}]})
    assert not result.success and result.error.code == ErrorCode.VALIDATION_ERROR
    assert (await service.call("list_midi_notes", midi)).data["total"] == 0


async def test_trim_and_split_source_time(service, midi):
    result = await service.call(
        "trim_region",
        {
            **midi,
            "start": {"unit": "bbt", "bar": 2, "beat": 1},
            "end": {"unit": "bbt", "bar": 9, "beat": 1},
        },
    )
    assert result.success
    region = await service.call("get_region", midi)
    assert region.data["position_samples"] == 96000 and region.data["source_start_ticks"] == 7680
    split = await service.call(
        "split_region", {**midi, "position": {"unit": "bbt", "bar": 3, "beat": 1}}
    )
    assert split.success and len(split.data["region_ids"]) == 2
    assert not (await service.call("get_region", midi)).success
    assert (await service.call("undo", {})).success
    assert (await service.call("get_region", midi)).data["source_start_ticks"] == 7680


def test_piecewise_tempo_conversion_roundtrip():
    t = Timeline()
    t.set_tempo(96000, 60)
    assert t.ticks_to_samples(15360) == 288000
    assert t.samples_to_ticks(288000) == 15360
    assert t.convert({"unit": "bbt", "bar": 3, "beat": 1, "tick": 0})["seconds"] == 6
    for sample in [0, 1, 47999, 96000, 123456, 1000000]:
        assert abs(t.ticks_to_samples(t.samples_to_ticks(sample)) - sample) <= 25


def test_meter_changes_and_beat_units():
    t = Timeline()
    t.set_meter(96000, 3, 8)
    assert t.bbt_to_ticks(2, 2, 0) == 8640
    assert t.ticks_to_bbt(10560) == {"bar": 3, "beat": 1, "tick": 0}
    with pytest.raises(DomainError):
        t.bbt_to_ticks(2, 4, 0)
    with pytest.raises(DomainError):
        t.bbt_to_ticks(2, 1, 1000)
    with pytest.raises(DomainError):
        t.set_meter(500, 3, 4)


async def test_note_constructor_integer_overflow_rejected(service, midi, backend):
    from ardour_ultra_mcp.models.time import MAX_QUARTER_TICKS

    before = backend.revision
    for start, duration in [
        (MAX_QUARTER_TICKS + 1, 1),
        (MAX_QUARTER_TICKS, 1),
        (0, MAX_QUARTER_TICKS + 1),
    ]:
        result = await service.call(
            "insert_midi_notes",
            {
                **midi,
                "notes": [
                    {
                        "pitch": 60,
                        "velocity": 100,
                        "channel": 1,
                        "start_ticks": start,
                        "duration_ticks": duration,
                    }
                ],
            },
        )
        assert not result.success and backend.revision == before
