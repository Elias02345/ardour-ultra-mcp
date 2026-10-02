"""Deterministic simulator measurements; real DAW timing is recorded by E2E harnesses."""

from __future__ import annotations

import asyncio
import json
import platform
import statistics
import time
from pathlib import Path

from ardour_ultra_mcp.backends.fake import FakeBackend
from ardour_ultra_mcp.services.control import ControlService


async def main() -> None:
    backend = FakeBackend()
    service = ControlService(backend)
    samples: dict[str, list[float]] = {}

    async def measure(label, command, args, iterations=10):
        values = []
        for _ in range(iterations):
            start = time.perf_counter()
            r = await service.call(command, args)
            values.append((time.perf_counter() - start) * 1000)
            assert r.success, r.error
        samples[label] = values
        return r

    track = await service.call("create_track", {"name": "Bass", "kind": "midi"})
    tid = track.data["id"]
    region = await service.call(
        "create_midi_region",
        {
            "track_id": tid,
            "name": "Benchmark notes",
            "start": {"unit": "samples", "samples": 0},
            "end": {"unit": "seconds", "seconds": 30},
        },
    )
    ref = {"track_id": tid, "region_id": region.data["id"]}
    await measure("simple_state_query", "get_track", {"track_id": tid})
    await measure("single_parameter_change", "set_track_gain", {"track_id": tid, "gain_db": -4.25})
    for count in [100, 10000]:
        await measure(
            f"insert_{count}_midi_notes",
            "insert_midi_notes",
            {
                **ref,
                "notes": [
                    {
                        "pitch": 48 + i % 12,
                        "velocity": 104,
                        "channel": 1,
                        "start_ticks": i * 240,
                        "duration_ticks": 240,
                    }
                    for i in range(count)
                ],
            },
            iterations=1,
        )
    await measure(
        "create_10000_automation_points",
        "create_automation_points",
        {
            "track_id": tid,
            "control": "gain",
            "unit": "linear_gain",
            "points": [
                {"position": {"unit": "samples", "samples": i * 100}, "value": 0.5}
                for i in range(10000)
            ],
        },
        iterations=1,
    )
    for i in range(100):
        backend._new_track(f"Track {i}", "audio", 2)  # fixture construction is outside measurement
    await measure("enumerate_102_tracks", "list_tracks", {"limit": 1000}, iterations=3)
    plugin = await service.call(
        "add_plugin", {"track_id": tid, "plugin_id": "urn:ultra:simulated:filter", "format": "LV2"}
    )
    await measure(
        "plugin_parameter_enumeration",
        "get_plugin_parameters",
        {"track_id": tid, "processor_id": plugin.data["processor_id"]},
        iterations=3,
    )
    result = {
        "scope": "simulator only; includes complete-content revision digest and undo snapshots; not real DAW latency",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "benchmarks": {
            k: {"iterations": len(v), "median_ms": statistics.median(v), "max_ms": max(v)}
            for k, v in samples.items()
        },
    }
    Path("artifacts/benchmarks.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
