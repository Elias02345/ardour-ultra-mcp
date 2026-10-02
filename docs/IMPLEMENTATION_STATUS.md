# Implementation status

Development release 0.1.0. Status describes executable code and validation, not an assurance of production readiness. Final measured evidence will be recorded in TESTING.md and FINAL_GAP_ANALYSIS.md.

| Area | Status | Scope |
|---|---|---|
| Research / architecture | DONE | Current stable/development source, official SDK v2, named peers; source inventories and transport benchmark |
| MCP tools/resources/prompts | PARTIAL | 71 typed tools, seven resources, one prompt registered; protocol validation in progress |
| Tracks / transport / mixer | PARTIAL | Native Lua handlers and OSC subset; real Ardour integration in progress |
| MIDI internal editing | PARTIAL | Exact note diffs and dense batches; guarded references, source-relative time; real Editor E2E pending |
| Plugins | PARTIAL | Inventory, instances, generic parameter batches/presets; runtime validation in progress |
| Regions | PARTIAL | Active-playlist move/trim/split/delete, gain/mute/lock/fade durations; source-backed handlers |
| Automation | PARTIAL | Native curves/mementos and modes; bounded reads; runtime validation in progress |
| Routing | PARTIAL | Sends and physical/backend ports; raw internal connections fail closed |
| Recording | PARTIAL | Arm/monitor/start/stop, active recording mutation guard; punch adapter pending |
| Analysis | PARTIAL | Optional bounded offline mono/stereo metrics, numerical validation in progress; estimated true peak labelled |
| Export | EXPERIMENTAL | SimpleExport master/preset/range only, isolated new directory; stems unavailable |
| Transactions | PARTIAL | Native edit diffs; compensated control batches; no general ACID/grouped control undo |
| State/concurrency | PARTIAL | Explicit queries; observed route/region revisions; exact MIDI model guards; no full human-edit generation |
| Installation | PARTIAL | Portable paths/script install/backups/config snippets; hook activation manual; external platform checks pending |
| Tests/CI/package | PARTIAL | Verification in progress |
| Linux | PARTIAL | Ardour 8.12 standalone runtime acquired; current 9.8 binary incompatible with host libc |
| macOS / Windows DAW | BLOCKED | No platform execution environment; pure Python CI configured but not run here |
| CC/bend/pressure/program/SysEx/MPE | UNSUPPORTED | No enabled mutation adapter with verified persistence |
| Groups/markers/metadata/session opening | UNSUPPORTED | Native primitives researched, complete safe adapters pending |
| Stretch/shift/crossfades/import/stems | UNSUPPORTED | Safe job/source/format adapters not yet validated |

Every disabled function remains in the capability gap manifest. The simulator does not render or execute real plugins. Unsupported calls return structured errors.
