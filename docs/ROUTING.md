# Mixing and routing

`list_tracks`/`get_track` return actual route mixer values and IDs. Gain requests use dB (-193..+6); -193 represents the tool's effective silence floor. Pan is stereo azimuth in signed normalized -1..+1, mapped to Ardour 0..1. Mute/solo/arm/monitoring are explicit setters. Group linkage is ignored using NoGroup; automation/VCA effects can still alter effective audio gain.

Create an audio bus with `create_track` kind bus. `create_send` takes a stable non-singleton source track/route and non-singleton audio bus target; `gain_db` is explicit. It checks the current graph of sends and main output edges for a feedback cycle before creation. Duplicate source-to-target sends return CONFLICT rather than creating hidden duplicates. Inspect `list_sends`; use stable send processor IDs for gain/removal. Sends to master/singletons are excluded because Ardour's add_internal_send rejects them.

```json
{"track_id":"BASS_ROUTE_ID","target_id":"SIDECHAIN_BUS_ID","gain_db":-6,"dry_run":true}
```

This creates an ordinary internal aux send when executed. It does **not** configure a plugin's sidechain detector. Sidechain pin/channel mapping is an explicit remaining gap.

`list_ports` reports backend-qualified names, directions, datatypes and connections. connect/disconnect validate existence/type/direction. Raw internal route-to-route connections fail closed until a complete feedback graph adapter is available; use checked sends. External/hardware connections are permitted only to actual engine ports. Renamed/backend-restarted ports may need fresh discovery.

Port namespace, metering, channel layout and plugin processing differ by audio backend. `get_meter_state` reads peak dBFS; it is a momentary meter observation, not offline true peak/clipping certification. Route groups have native 9.8 list/create/properties/membership/removal tools. Singleton routes are excluded; transfer from another group requires explicit membership removal. Removing the last member deletes an ordinary group. Empty groups cannot be removed through the tested Ardour binding. Group operations are not natively undoable. Output rerouting/reorder, send pan, parallel/reverb helpers and additional ensure_* workflows remain gaps. ensure_bus creates at most one exact-name/channel-count bus, rejects ambiguous/non-bus collisions, checks revisions between pages/creation and returns existing IDs without changing them.
