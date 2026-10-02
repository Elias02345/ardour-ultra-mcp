from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import Finite, Model, Name, ObjectId, Options, Samples
from .time import MAX_QUARTER_TICKS, Position, QuarterTicks


class Empty(Options):
    pass


class Page(Options):
    offset: Annotated[int, Field(ge=0, le=10000000)] = 0
    limit: Annotated[int, Field(ge=1, le=1000)] = 100
    name_filter: str = Field(default="", max_length=200)


class TrackRef(Options):
    track_id: ObjectId


class TrackPage(Page):
    track_id: ObjectId


class CreateTrack(Options):
    name: Name
    kind: Literal["audio", "midi", "bus"]
    channels: Annotated[int, Field(ge=1, le=64)] = 2


class RenameTrack(TrackRef):
    name: Name


class TrackGain(TrackRef):
    gain_db: Annotated[Finite, Field(ge=-193, le=6)]


class TrackPan(TrackRef):
    pan: Annotated[Finite, Field(ge=-1, le=1)] = Field(
        description="Signed normalized azimuth: -1 left, 0 center, +1 right; stereo azimuth only"
    )


class TrackToggle(TrackRef):
    enabled: bool


class Monitoring(TrackRef):
    mode: Literal["auto", "input", "disk"]


class Locate(Options):
    position: Position


class TimeRange(Options):
    start: Position
    end: Position


class Tempo(Locate):
    bpm: Annotated[Finite, Field(ge=1, le=999)] = Field(
        description="Quarter notes per minute; constant tempo point"
    )


class Meter(Locate):
    numerator: Annotated[int, Field(ge=1, le=128)]
    denominator: Literal[1, 2, 4, 8, 16, 32, 64]


class Snapshot(Options):
    name: Name = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,99}$")


class RegionRef(TrackRef):
    region_id: ObjectId


class RegionPage(TrackPage):
    kind: Literal["all", "audio", "midi"] = "all"


class CreateMidiRegion(TrackRef):
    name: Name
    start: Position
    end: Position


class MoveRegion(RegionRef):
    position: Position


class TrimRegion(RegionRef):
    start: Position
    end: Position


class SplitRegion(RegionRef):
    position: Position


class RegionGain(RegionRef):
    gain_db: Annotated[Finite, Field(ge=-193, le=24)]


class RegionToggle(RegionRef):
    enabled: bool


class Fades(RegionRef):
    fade_in_samples: Samples
    fade_out_samples: Samples


class MidiNote(Model):
    pitch: Annotated[int, Field(strict=True, ge=0, le=127)]
    velocity: Annotated[int, Field(strict=True, ge=1, le=127)]
    channel: Annotated[int, Field(strict=True, ge=1, le=16)] = 1
    start_ticks: QuarterTicks = Field(
        description="Source-relative quarter-note ticks; 1920 ticks per quarter; get region source offset before editing trimmed regions"
    )
    duration_ticks: Annotated[int, Field(strict=True, ge=1, le=MAX_QUARTER_TICKS)]

    @model_validator(mode="after")
    def check_note_end(self) -> MidiNote:
        if self.start_ticks + self.duration_ticks > MAX_QUARTER_TICKS:
            raise ValueError("Note end exceeds Ardour signed 32-bit beat constructor range")
        return self


class InsertNotes(RegionRef):
    notes: Annotated[list[MidiNote], Field(min_length=1, max_length=10000)]


class MidiPage(RegionRef):
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=1000)] = 100


class NoteReplacement(Model):
    note_ref: str = Field(min_length=1, max_length=250)
    note: MidiNote


class EditNotes(RegionRef):
    model_fingerprint: str = Field(min_length=1, max_length=160)
    replacements: Annotated[list[NoteReplacement], Field(min_length=1, max_length=10000)]


class DeleteNotes(RegionRef):
    model_fingerprint: str = Field(min_length=1, max_length=160)
    note_refs: Annotated[list[str], Field(min_length=1, max_length=10000)]


class PluginInventory(Page):
    instruments_only: bool = False


class PluginRef(TrackRef):
    processor_id: ObjectId


class AddPlugin(TrackRef):
    plugin_id: str = Field(min_length=1, max_length=1000)
    format: Literal["LV2", "LADSPA", "Lua", "VST3", "Windows_VST", "LXVST", "MacVST", "AudioUnit"]
    index: Annotated[int, Field(ge=0, le=4096)] = 0


class PluginToggle(PluginRef):
    enabled: bool


class PluginPage(PluginRef):
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=1000)] = 100


class ParameterValue(Model):
    parameter_index: Annotated[int, Field(ge=0, le=65535)] = Field(
        description="Ardour nth_parameter ordinal, not plugin port ID"
    )
    value: Finite = Field(description="Native plugin value; not normalized; use inspected metadata")
    unit: str = Field(
        default="plugin_native",
        max_length=100,
        description="Must match reported unit; plugin_native when physical unit is unavailable",
    )


class SetParameters(PluginRef):
    parameters: Annotated[list[ParameterValue], Field(min_length=1, max_length=4096)]


class Preset(PluginRef):
    label: Name


class SendRef(TrackRef):
    send_id: ObjectId


class CreateSend(TrackRef):
    target_id: ObjectId
    gain_db: Annotated[Finite, Field(ge=-193, le=6)] = -6


class SendGain(SendRef):
    gain_db: Annotated[Finite, Field(ge=-193, le=6)]


class PortConnection(Options):
    source: str = Field(min_length=1, max_length=500, pattern=r"^[^\x00-\x1f]+$")
    destination: str = Field(min_length=1, max_length=500, pattern=r"^[^\x00-\x1f]+$")


class AutomationTarget(TrackRef):
    control: Literal["gain", "pan", "plugin", "send"]
    processor_id: ObjectId | None = None
    parameter_index: Annotated[int, Field(ge=0, le=65535)] | None = None

    @model_validator(mode="after")
    def check_target(self) -> AutomationTarget:
        if self.control in {"plugin", "send"} and self.processor_id is None:
            raise ValueError("processor_id required for plugin/send automation")
        if self.control == "plugin" and self.parameter_index is None:
            raise ValueError("parameter_index required for plugin automation")
        if self.control != "plugin" and self.parameter_index is not None:
            raise ValueError("parameter_index only applies to plugin automation")
        if self.control in {"gain", "pan"} and self.processor_id is not None:
            raise ValueError("processor_id only applies to plugin/send automation")
        return self


class AutomationPoint(Model):
    position: Position
    value: Finite = Field(
        description="Native control units: gain/send linear coefficient, pan 0..1, plugin_native"
    )


class AutomationPoints(AutomationTarget):
    points: Annotated[list[AutomationPoint], Field(min_length=1, max_length=10000)]
    unit: Literal["linear_gain", "normalized_azimuth", "plugin_native"]
    replace: bool = False
    interpolation: Literal["linear", "discrete"] = "linear"


class AutomationMode(AutomationTarget):
    mode: Literal["off", "play", "write", "touch", "latch"]


class AnalyzeFile(Options):
    path: str = Field(min_length=1, max_length=4000)
    max_seconds: Annotated[Finite, Field(gt=0, le=3600)] = 600


class CompareFiles(Options):
    first: str = Field(min_length=1, max_length=4000)
    second: str = Field(min_length=1, max_length=4000)
    max_seconds: Annotated[Finite, Field(gt=0, le=3600)] = 600


class Render(TimeRange):
    output_directory: str = Field(
        min_length=1,
        max_length=4000,
        description="New empty directory under an explicitly allowed export root",
    )
    name: Name
    preset_id: str = Field(
        default="",
        max_length=200,
        pattern=r"^[A-Za-z0-9-]*$",
        description="Existing Ardour export preset UUID; empty uses SimpleExport default; format defined by preset",
    )


class BatchItem(Model):
    command: str = Field(min_length=1, max_length=100)
    arguments: dict[str, object] = Field(default_factory=dict)


class Batch(Options):
    name: Name = "Ultra MCP batch"
    operations: Annotated[list[BatchItem], Field(min_length=1, max_length=100)]
