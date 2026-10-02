# Migration from raibid-entertainment/ardour-mcp

This is an independent clean-room replacement, not a fork or drop-in upgrade. No peer code is incorporated. Preserve existing sessions and any working controller configuration; evaluate Ultra in a disposable session before switching clients.

Existing OSC strip indices must become actual Ardour IDs returned by list_tracks/get_track. Pan conventions differ: Ultra uses signed normalized -1..+1 for the mixer; direct native automation uses 0..1. Ultra accepts a typed MCP request object, explicit unit models, pagination, guarded note references and structured errors. Track names are context, not unique identity. Mutations should use available capabilities, preflight and readback.

Legacy names are not automatically aliased where semantics differ or unverified upstream endpoints were assumed. create_track with explicit kind replaces separate track-creation wrappers. insert_midi_notes edits Ardour's internal model rather than an external MIDI-generation/import service. MIDI operations do not require the legacy MIDI server.

Lua hook installation is required for deep control; OSC remains optional. Existing Ardour OSC ports may stay configured if used by another controller, but do not expose them beyond intended local access. Configure a separate Ultra MCP entry initially. No migration command rewrites existing client/config files or session XML.
