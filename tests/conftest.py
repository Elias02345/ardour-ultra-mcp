import pytest

from ardour_ultra_mcp.backends.fake import FakeBackend
from ardour_ultra_mcp.services.control import ControlService


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def service(backend):
    return ControlService(backend)


@pytest.fixture
async def midi(service):
    result = await service.call("create_track", {"name": "Bass", "kind": "midi"})
    assert result.success
    track_id = result.data["id"]
    result = await service.call(
        "create_midi_region",
        {
            "track_id": track_id,
            "name": "Bass pattern",
            "start": {"unit": "bbt", "bar": 1, "beat": 1},
            "end": {"unit": "bbt", "bar": 9, "beat": 1},
        },
    )
    assert result.success
    return {"track_id": track_id, "region_id": result.data["id"]}


@pytest.fixture
async def plugin(service):
    track = await service.call("create_track", {"name": "Synth", "kind": "midi"})
    result = await service.call(
        "add_plugin",
        {"track_id": track.data["id"], "plugin_id": "urn:ultra:simulated:synth", "format": "LV2"},
    )
    assert result.success
    return {"track_id": track.data["id"], "processor_id": result.data["processor_id"]}
