# Automation

Supported targets: route gain, route pan azimuth, internal send gain, and generic plugin controls where Ardour exposes their AutomationList. Target requests use stable track/processor IDs and parameter ordinal for plugins.

```json
{"track_id":"ROUTE_ID","control":"gain","unit":"linear_gain","points":[{"position":{"unit":"bbt","bar":1,"beat":1},"value":0.5},{"position":{"unit":"bbt","bar":4,"beat":1},"value":0.8}],"interpolation":"linear"}
```

Gain/send curves use **linear coefficients**, not dB: `10^(dB/20)`. Pan curves use normalized azimuth 0..1; mixer pan tools use signed -1..+1. Plugin curves use plugin_native after descriptor inspection. The request unit must match the target. Values are range checked against the native descriptor. No physical Hz unit is assumed from the displayed parameter name.

`create_automation_points` accepts up to 10,000 points, sorts them and rejects duplicate positions. The resulting native list, including any existing points and Ardour zero anchor, must also fit 10,000. Existing exact positions are updated. New points use ControlList.editor_add so constant-value rows are preserved; the recording-oriented add method would coalesce them. On a fresh curve beginning after sample zero, Ardour inserts a matching zero anchor. Results expose anchor_at_zero_added, requested point_count and actual_point_count; preflight includes that anchor. Replacement requires `replace: true` and confirm_delete (unless dry_run). `get_automation` returns current points, explicit units and available mode/range metadata; native reads above 10,000 points currently fail closed rather than pretend pagination exists. `clear_automation` requires confirm_delete. Modes off/play/write/touch/latch are explicit; recording guards prevent edits during active recording and the bridge refuses an active automation write pass.

Native curves use memento commands for one-step undo. Failure rollback requires the Editor context; a standalone runtime may return OUTCOME_UNCERTAIN. Only linear/discrete interpolation is enabled. Complex bezier curves, complete lane inventory, and point-specific persistent identities are not implemented.
