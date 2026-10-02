# Internal MIDI editing

The bridge edits Ardour MidiModel directly using NoteDiffCommand; it does not generate an external MIDI file as its editing strategy. Region creation uses the bound Editor/MidiTimeAxisView API in 9.8 source; older builds without that binding return BACKEND_UNSUPPORTED. Existing-region note editing is a separate capability.

`create_midi_region` request:

```json
{"track_id":"ARDOUR_ROUTE_ID","name":"Bass phrase","start":{"unit":"bbt","bar":1,"beat":1,"tick":0},"end":{"unit":"bbt","bar":9,"beat":1,"tick":0}}
```

`insert_midi_notes` request:

```json
{"track_id":"ARDOUR_ROUTE_ID","region_id":"ARDOUR_REGION_ID","notes":[{"pitch":48,"velocity":108,"channel":1,"start_ticks":0,"duration_ticks":240},{"pitch":48,"velocity":94,"channel":1,"start_ticks":240,"duration_ticks":240}]}
```

A quarter note is **1920 ticks**, taken from Ardour Temporal. Tick position is source-relative, not implicitly session-relative. Channels are 1..16 and translated to Ardour's zero-based model channels. Velocity 1..127 (zero is note-off, not an inserted note). Duration must be positive. Pitch 48 is MIDI number 48; octave naming varies among DAWs.

Convert session BBT with `convert_position` and inspect `get_region`. Convert the region's position_samples to session quarter ticks too. The exact formula is **note source ticks = target session quarter ticks − region position session quarter ticks + source_start_ticks**. Do not subtract source_start_ticks alone. Trimmed/shared-source regions may contain notes outside the visible region. `list_midi_notes` explicitly returns source scope and pagination.

Batch insertion accepts up to 10,000 notes in one call/native diff. Duplicate exact notes are allowed. Editing and deletion first require `list_midi_notes`: retain `model_fingerprint` and the returned `note_ref`. `edit_midi_notes` replaces explicitly selected notes using remove/add diffs, enabling move, duration, velocity, channel and transposition changes. `delete_midi_notes` accepts references and requires confirm_delete. Every stale or duplicate reference is rejected before mutation. Fingerprints are opaque, not persistent note UUIDs; refresh after undo, edits, session/hook restart or snapshot expiry.

Quantization, humanization and theory helpers are not separate tools. An agent can calculate exact replacement batches using the atomic schema. MIDI CC, pitch bend, pressure, program changes, SysEx and MPE mutation adapters are disabled until persistence and event semantics are independently validated. No claim that all musical production workflows are complete.

`copy_region` takes target_track_id, name and a typed absolute timeline position. MIDI copies explicitly fork the internal source so later note edits are independent; audio copies share their source nondestructively. The adapter resolves the actual inserted ID because Playlist::add_region can create a further instance for whole-file regions. Playlist insertion has native undo; undo may leave an unused session source, so this is not a disk-file rollback promise.

Guard snapshots are bounded to 32 entries and 16 MiB of exact model signatures. Listing another page of an unchanged model reuses its opaque fingerprint instead of duplicating dense signatures. Eviction makes old references stale; relist rather than guessing a note identity.

Insertion returns inserted_count; guarded edit/delete returns changed_count. The simulator uses the same count fields, with additional labelled state metadata. Native route/region/processor/group IDs are canonical unsigned 64-bit decimal strings; UUIDs/prefixed simulator IDs are not interchangeable with these objects.
