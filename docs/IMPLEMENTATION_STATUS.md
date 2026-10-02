# Implementation status

Development release 0.1.0, evidence dated 2026-10-02. Status refers to delivered code within its stated scope, not full production readiness. Exact final counts/results are in TESTING.md and artifacts; broader gaps are in FINAL_GAP_ANALYSIS.md.

| Area | Status | Scope |
|---|---|---|
| Research / architecture | DONE | Stable 9.8 and development source/manual; official MCP v2/spec; named peers/licenses; transport prototypes and evidence matrix |
| MCP foundation | DONE | 80 typed tools, seven resources, one prompt; actual official-client STDIO/schema/progress tests |
| Tracks / transport / mixer | PARTIAL | Exact stable-ID route controls and async transport; native Linux subset; clone/reorder/IO gaps |
| Internal MIDI | PARTIAL | Native 9.8 region creation, 100/10,000-note batches, guarded edit/delete, independent copy and undo/redo tested; controller-event adapters missing |
| Plugins | PARTIAL | Generic native inventory/instruments, parameters, presets, activation/insertion/removal; tested LV2; format/reorder/state gaps |
| Regions | PARTIAL | Native fixture verifies gain/fades/mute/lock/move/trim/split/copy/delete and undo; audio import/advanced processing incomplete |
| Automation | PARTIAL | Native curves/memento undo, explicit units/modes, 10,000-point batching; bounded reads and limited lane enumeration |
| Routing | PARTIAL | Native sends and backend ports, loop checks; sidechain pins and raw internal routing disabled |
| Groups | PARTIAL | 9.8 native IDs/membership/properties verified; 8.12 mutation gated, empty-group API limitation explicit |
| Recording | PARTIAL | Arm/monitor/start/stop and active-recording editing guard; hardware/punch E2E pending |
| Local analysis | DONE | Implemented bounded offline metrics numerically tested; estimated true peak explicitly labelled; optional dependencies |
| Master export | EXPERIMENTAL | Real 9.8 preset/range/master export and analysis loop; no stems/format setter claims |
| Transactions / safety | PARTIAL | Native note/region/automation undo; prevalidated compensated controls, explicit destructive intent/preflight; no general ACID |
| State / concurrency | PARTIAL | Fresh actual reads, scoped route/region/group revisions and exact MIDI guards; complete human-edit generation/cache missing |
| Install / CLI / clients | PARTIAL | Portable paths/backups/version probes/doctor/config printing; manual hook activation; client applications not launched |
| Tests / package / CI | PARTIAL | 112 tests on each of Python 3.12/3.14; 39/47 native common checks and 74 native EditorHook checks; 84.44% combined Python branch/statement coverage; hosted OS matrix not executed |
| Linux | PARTIAL | Real 8.12 common and 9.8 common/editor on x86_64 Dummy; hardware/other distributions/ARM external |
| macOS / Windows DAW | BLOCKED | No native platform environment; code paths/pure Python CI require external execution |
| MIDI CC/bend/pressure/program/SysEx/MPE | UNSUPPORTED | No enabled persistence-verified mutation adapter |
| Markers/ranges | UNSUPPORTED | Native Location ID probe unreliable; safe identity and undo adapter pending |
| Metadata/session opening/save-as/timecode | UNSUPPORTED | Safe lifecycle/binding/conversion adapters pending |
| Stretch/shift/crossfades/import/stems | UNSUPPORTED | Safe jobs/source/export adapters pending; not claimed impossible in Ardour |
| Production workflows | PARTIAL | ensure_bus and render_and_analyze with explicit outcomes; deeper chains/sidechain helpers pending |

The simulator cannot execute actual plugins or render audio. A registered tool can be unavailable on a running backend; discovery and calls fail explicitly. No unsupported feature is represented by a fake success.
