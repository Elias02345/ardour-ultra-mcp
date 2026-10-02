"""One source of truth for command schemas, capabilities and generated documentation."""

from dataclasses import dataclass

from pydantic import JsonValue

from ..models import requests as r
from ..models.base import Options


@dataclass(frozen=True)
class ToolSpec:
    name: str
    request: type[Options]
    category: str
    description: str
    mutates: bool = False
    destructive: bool = False
    local: bool = False


SPECS: tuple[ToolSpec, ...] = (
    ToolSpec("ping", r.Empty, "system", "Check backend heartbeat and current session."),
    ToolSpec(
        "get_capabilities",
        r.Empty,
        "system",
        "Return truthful per-command backend capability status.",
        local=True,
    ),
    ToolSpec(
        "get_server_info",
        r.Empty,
        "system",
        "Server version, MCP SDK, platform and protocol details.",
        local=True,
    ),
    ToolSpec(
        "doctor",
        r.Empty,
        "system",
        "Inspect runtime, bridge, paths and optional analysis dependencies.",
        local=True,
    ),
    ToolSpec(
        "get_session_info",
        r.Empty,
        "session",
        "Read session UUID, name, sample rate and observed revision scope.",
    ),
    ToolSpec(
        "save_session", r.Empty, "session", "Save current session through Ardour save_state.", True
    ),
    ToolSpec(
        "create_snapshot",
        r.Snapshot,
        "session",
        "Save a named snapshot without replacing an existing snapshot.",
        True,
    ),
    ToolSpec(
        "list_tracks", r.Page, "tracks", "Paginate routes with stable Ardour IDs and mixer state."
    ),
    ToolSpec("get_track", r.TrackRef, "tracks", "Inspect a route by persistent Ardour ID."),
    ToolSpec(
        "create_track",
        r.CreateTrack,
        "tracks",
        "Create an audio/MIDI track or audio bus using Session APIs.",
        True,
    ),
    ToolSpec(
        "delete_track",
        r.TrackRef,
        "tracks",
        "Delete a non-singleton route; explicit confirm_delete required; not natively undoable.",
        True,
        True,
    ),
    ToolSpec("rename_track", r.RenameTrack, "tracks", "Rename a stable-ID route.", True),
    ToolSpec(
        "set_track_gain",
        r.TrackGain,
        "mixer",
        "Set route gain in dB (-193..+6), ignoring group linkage.",
        True,
    ),
    ToolSpec(
        "set_track_pan",
        r.TrackPan,
        "mixer",
        "Set stereo azimuth in signed normalized units -1..+1.",
        True,
    ),
    ToolSpec("set_track_mute", r.TrackToggle, "mixer", "Set route mute explicitly.", True),
    ToolSpec("set_track_solo", r.TrackToggle, "mixer", "Set route solo explicitly.", True),
    ToolSpec(
        "arm_track", r.TrackToggle, "recording", "Set recording arm on a recordable track.", True
    ),
    ToolSpec(
        "set_monitoring", r.Monitoring, "recording", "Set track monitoring: auto/input/disk.", True
    ),
    ToolSpec(
        "get_meter_state",
        r.TrackRef,
        "metering",
        "Read route peak meter values in dBFS; no audio analysis in realtime.",
    ),
    ToolSpec(
        "get_transport",
        r.Empty,
        "transport",
        "Read playhead in samples, speed, loop and recording state.",
    ),
    ToolSpec(
        "play",
        r.Empty,
        "transport",
        "Request playback. Inspect get_transport to confirm asynchronous state.",
        True,
    ),
    ToolSpec("stop", r.Empty, "transport", "Request transport stop.", True),
    ToolSpec(
        "locate",
        r.Locate,
        "transport",
        "Locate using typed samples, seconds, quarter ticks or BBT.",
        True,
    ),
    ToolSpec(
        "start_recording",
        r.Empty,
        "recording",
        "Enable session recording and request roll; arm tracks first.",
        True,
    ),
    ToolSpec(
        "stop_recording",
        r.Empty,
        "recording",
        "Stop transport and disable session recording.",
        True,
    ),
    ToolSpec(
        "set_loop",
        r.TimeRange,
        "transport",
        "Update an existing Ardour loop location and enable loop.",
        True,
    ),
    ToolSpec("clear_loop", r.Empty, "transport", "Disable loop playback.", True),
    ToolSpec(
        "convert_position",
        r.Locate,
        "timeline",
        "Convert a typed position using Ardour's current tempo/meter map.",
    ),
    ToolSpec(
        "set_tempo",
        r.Tempo,
        "timeline",
        "Insert constant quarter-note BPM point at a typed position.",
        True,
    ),
    ToolSpec(
        "set_time_signature",
        r.Meter,
        "timeline",
        "Insert a time signature point through TempoMap.",
        True,
    ),
    ToolSpec(
        "list_regions",
        r.RegionPage,
        "regions",
        "Paginate active-playlist regions by route ID and kind.",
    ),
    ToolSpec(
        "get_region",
        r.RegionRef,
        "regions",
        "Read region ID, playlist, source offset, timeline position and length.",
    ),
    ToolSpec(
        "create_midi_region",
        r.CreateMidiRegion,
        "midi",
        "Create a blank internal MIDI region in Editor context.",
        True,
    ),
    ToolSpec(
        "move_region",
        r.MoveRegion,
        "regions",
        "Move a region nondestructively; named native undo.",
        True,
    ),
    ToolSpec(
        "trim_region",
        r.TrimRegion,
        "regions",
        "Trim to absolute timeline bounds within original region; native undo.",
        True,
    ),
    ToolSpec(
        "split_region",
        r.SplitRegion,
        "regions",
        "Split inside a region using its owning playlist; native undo.",
        True,
    ),
    ToolSpec(
        "delete_region",
        r.RegionRef,
        "regions",
        "Remove a region from active playlist with native undo and explicit delete intent.",
        True,
        True,
    ),
    ToolSpec(
        "set_region_gain",
        r.RegionGain,
        "regions",
        "Set audio-region amplitude in dB nondestructively.",
        True,
    ),
    ToolSpec(
        "set_region_mute", r.RegionToggle, "regions", "Set region mute with native undo.", True
    ),
    ToolSpec(
        "set_region_lock",
        r.RegionToggle,
        "regions",
        "Set region lock state with native undo.",
        True,
    ),
    ToolSpec(
        "set_region_fades",
        r.Fades,
        "regions",
        "Set audio fade durations in samples; preserve current fade shapes.",
        True,
    ),
    ToolSpec(
        "list_midi_notes",
        r.MidiPage,
        "midi",
        "Paginate internal notes with source-relative 1920-quarter ticks and guarded model references.",
    ),
    ToolSpec(
        "insert_midi_notes",
        r.InsertNotes,
        "midi",
        "Insert up to 10000 exact internal notes in one native note-diff undo command.",
        True,
    ),
    ToolSpec(
        "edit_midi_notes",
        r.EditNotes,
        "midi",
        "Replace guarded notes atomically in one native diff; pitch/time/length/velocity/channel.",
        True,
    ),
    ToolSpec(
        "delete_midi_notes",
        r.DeleteNotes,
        "midi",
        "Remove guarded notes in one diff; model fingerprint and explicit delete intent required.",
        True,
        True,
    ),
    ToolSpec(
        "list_available_plugins",
        r.Page,
        "plugins",
        "Query Ardour inventory; filter names/categories; formats are runtime dependent.",
    ),
    ToolSpec(
        "list_track_plugins",
        r.TrackPage,
        "plugins",
        "Paginate plugin instances with stable processor IDs.",
    ),
    ToolSpec(
        "add_plugin",
        r.AddPlugin,
        "plugins",
        "Load inventory-selected plugin ID/format and insert at processor index.",
        True,
    ),
    ToolSpec(
        "remove_plugin",
        r.PluginRef,
        "plugins",
        "Remove plugin processor with explicit intent; not natively undoable.",
        True,
        True,
    ),
    ToolSpec(
        "set_plugin_enabled", r.PluginToggle, "plugins", "Set plugin processor active state.", True
    ),
    ToolSpec(
        "get_plugin_parameters",
        r.PluginPage,
        "plugins",
        "Inspect parameter ordinal/port ID, native value, range/default and available display metadata.",
    ),
    ToolSpec(
        "set_plugin_parameters",
        r.SetParameters,
        "plugins",
        "Validate and set a batch of native parameter values; rollback supported values on failure.",
        True,
    ),
    ToolSpec(
        "list_plugin_presets", r.PluginRef, "plugins", "List loaded plugin's available presets."
    ),
    ToolSpec(
        "load_plugin_preset",
        r.Preset,
        "plugins",
        "Load an existing plugin preset by exact label.",
        True,
    ),
    ToolSpec(
        "list_sends",
        r.TrackPage,
        "routing",
        "List sends with stable processor and target route IDs.",
    ),
    ToolSpec(
        "create_send",
        r.CreateSend,
        "routing",
        "Create an internal aux send to a bus; reject routing feedback cycles.",
        True,
    ),
    ToolSpec("set_send_gain", r.SendGain, "routing", "Set send level in dB.", True),
    ToolSpec(
        "remove_send", r.SendRef, "routing", "Remove send with explicit delete intent.", True, True
    ),
    ToolSpec(
        "list_ports",
        r.Page,
        "routing",
        "Paginate engine port names and connections; port IDs are backend-qualified names.",
    ),
    ToolSpec(
        "connect_ports",
        r.PortConnection,
        "routing",
        "Connect valid output to input with matching data type.",
        True,
    ),
    ToolSpec(
        "disconnect_ports",
        r.PortConnection,
        "routing",
        "Disconnect one exact existing port connection.",
        True,
    ),
    ToolSpec(
        "get_automation",
        r.AutomationTarget,
        "automation",
        "Inspect automation points and mode for gain, pan, plugin or send.",
    ),
    ToolSpec(
        "create_automation_points",
        r.AutomationPoints,
        "automation",
        "Batch exact points with explicit native units; replace requires delete intent; native memento undo.",
        True,
    ),
    ToolSpec(
        "clear_automation",
        r.AutomationTarget,
        "automation",
        "Clear target automation with explicit delete intent and native undo.",
        True,
        True,
    ),
    ToolSpec(
        "set_automation_mode",
        r.AutomationMode,
        "automation",
        "Set native off/play/write/touch/latch mode.",
        True,
    ),
    ToolSpec(
        "undo",
        r.Empty,
        "transactions",
        "Invoke Editor native undo once; only native undoable edits are guaranteed.",
        True,
    ),
    ToolSpec("redo", r.Empty, "transactions", "Invoke Editor native redo once.", True),
    ToolSpec(
        "execute_batch",
        r.Batch,
        "transactions",
        "Prevalidate compensable control edits and apply with rollback; no general ACID promise.",
        True,
    ),
    ToolSpec(
        "render_range",
        r.Render,
        "export",
        "Export master range using actual Ardour preset into a new isolated directory.",
        True,
    ),
    ToolSpec(
        "analyze_audio_file",
        r.AnalyzeFile,
        "analysis",
        "Offline peak/RMS/LUFS/spectrum/stereo/silence and estimated true peak; allowed roots only.",
        local=True,
    ),
    ToolSpec(
        "compare_audio_files",
        r.CompareFiles,
        "analysis",
        "Compare two measured passes; no subjective quality score.",
        local=True,
    ),
)
CATALOG = {spec.name: spec for spec in SPECS}
COMPENSABLE = frozenset(
    {
        "rename_track",
        "set_track_gain",
        "set_track_pan",
        "set_track_mute",
        "set_track_solo",
        "set_send_gain",
        "set_plugin_parameters",
        "set_plugin_enabled",
    }
)
UNSUPPORTED: dict[str, JsonValue] = {
    "persistent_note_ids": "Ardour NotePtr does not expose event ID in Lua.",
    "midi_cc_editing": "Model/persistence semantics not yet integration verified.",
    "midi_sysex_editing": "Event data buffer and safe construction not sufficiently bound.",
    "mpe_editing": "No verified MPE model edit adapter.",
    "render_stems": "SimpleExport exposes master output, not stem selection.",
    "time_stretch": "Offline helper needs safe asynchronous job adapter.",
    "pitch_shift": "Offline helper needs safe asynchronous job adapter.",
    "crossfades": "Dedicated deterministic crossfade adapter not verified.",
    "session_open_create": "Live GUI session replacement/creation not verified safely.",
    "save_session_as": "Live relocation semantics not verified.",
    "scan_plugins": "Inventory available; forcing plugin scan not bound safely.",
    "import_audio": "Editor import arguments and precise insertion not integration verified.",
    "full_human_edit_revision": "Bridge revision observes supported state; no complete Ardour generation API.",
    "general_atomic_transactions": "Ardour abort_reversible_command discards history, not edits.",
    "timecode_conversion": "Typed drop-frame/offset conversion adapter pending validation.",
    "session_metadata": "Complete metadata accessor not bound/validated.",
    "groups": "Native bindings found; implementation and integration coverage pending.",
    "markers": "Range primitives found; complete creation/undo adapter pending.",
    "punch_configuration": "Existing location/config bindings require additional verification.",
}
