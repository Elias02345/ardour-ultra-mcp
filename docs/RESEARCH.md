# Research — 2026-10-02

This is an original implementation, not a fork. Upstream code was read for API evidence and design review; no peer implementation code is incorporated. Exact repository commits and commit dates are in [sources.json](../research/sources.json). Source inventories capture registered OSC methods and Lua bindings, including class context and line numbers. Research observations are distinct from integration validation.

## Authoritative versions and sources

* [Ardour homepage](https://ardour.org/) advertises **9.8**. [9.8 source](https://github.com/Ardour/ardour/tree/22ed8656c2533e325322ff11831448e5123e0d4b) and current master were inspected separately. Ardour is GPL-2.0-or-later; third-party portions have their own notices. Windows/macOS plugin support is conditional on build flags.
* [Ardour manual](https://manual.ardour.org/): OSC, Lua, editing, plugins, export and scripting reference; source takes precedence when manual coverage is incomplete. The manual checkout date and revision are recorded.
* [Official Python SDK](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0): **2.2.0**, stable release 2026-09-07; PyPI metadata independently agrees. Use `from mcp.server import MCPServer`, not tutorial-era FastMCP. MIT license.
* [MCP specification](https://modelcontextprotocol.io/specification/2026-07-28): current published 2026-07-28 revision; SDK negotiates prior versions. Standard local STDIO, tools with schemas and structured content, resources, prompts, progress where useful. Logging/roots details changed in this revision; rely on the official SDK for protocol behavior. Server diagnostics go to stderr.

## Ardour interfaces

Primary evidence: `libs/surfaces/osc/osc.cc`, `osc_strip_observer.cc`, `osc_global_observer.cc`; `libs/ardour/luabindings.cc`, `lua_api.cc`; `gtk2_ardour/luainstance.cc`, `luasignal.h`, `midi_time_axis.cc`; `libs/lua/luastate.cc`; `libs/pbd/history_owner.cc`; `libs/ardour/simple_export.cc`. Links below refer to the 9.8 source unless noted.

OSC has transport, locate (`ii`, signed 32-bit samples), record controls, loop/punch toggles, strip gain in dB, pan in 0..1, mute/solo, monitoring, send level, plugin instance/parameter enumeration, activation and raw parameter changes. `/strip/list` returns presentation-based strip numbers, not persistent IDs. `/set_surface` configures reply/feedback behavior. Send success is not an acknowledgement of a completed mutation. UDP packets can be lost, and OSC strip addressing can change on reorder. Therefore OSC alone cannot meet precise editing and identity requirements. No MIDI note editor, region creation/splitting, generic plugin instantiation or true transactions is registered. `/access_action` runs known actions; it is not a query/edit API and selection-dependent actions cannot provide deterministic object addressing. Ardour's own liblo server does not explicitly bind to loopback: enabling it can expose Ardour to the LAN. The Python receiver must bind to loopback, and users must firewall Ardour's OSC port.

Lua bindings expose Session UUID, Stateful ID, route/processor lookup, route and track creation/removal, active playlists, region lookup/editing, automation, plugin inventory and generic loading, plugin descriptors/presets, engine ports/connections, internal sends, groups, locations and tempo maps. A registered **EditorHook** with `LuaTimerDS` executes on the GTK event context (100 ms timer), outside the audio processing callback. It may still stall the UI; bounded batches and recording guards are required. DSP and Session scripts can execute in the realtime context and are unsuitable for file IPC. `LuaState::sandbox(false)` removes `require` and `package` but retains `io`/`os`; no LuaSocket assumption is valid. Official example `periodic_backup.lua` confirms timer and snapshot use. LuaOSC binds a sender only, not a general receiving server. File IPC is portable using retained `io.open`, `os.rename` and a single privately owned directory. Never parse incoming Lua expressions with `load` or execute arbitrary commands.

### Object/editing evidence and limits

| Area | Verified binding/source | Consequence |
|---|---|---|
| Identity | Session `uuid`, Stateful `id():to_s`, `route_by_id`, `processor_by_id`, RegionFactory `region_by_id` | Persistent Ardour IDs, not invented UUIDs; ports identified by backend-qualified names |
| MIDI | LuaAPI `new_noteptr`, `note_list`; MidiModel `new_note_diff_command`, `add`, `remove`, `apply_diff_command_as_commit` | Internal batch insertion and remove/add replacements; no external SMF editing required |
| MIDI region creation | Editor `rtav_from_route`, MidiTimeAxisView `add_region(position, length, commit)` | Requires Editor context; cannot claim headless LuaSession has Editor |
| MIDI identity | NotePtr only exposes time/pitch/velocity/length/channel | No persistent note ID; use optimistic guarded references tied to a model fingerprint, reject stale references |
| MIDI CC/pressure/bend | AutomatableSequence, Evoral Parameter and automation controls | Plausible, must verify model persistence and event semantics before enabling |
| Program/SysEx | Diff commands and read lists exist; event buffer not bound; duplicate class-name registrations occur | Program/SysEx mutation and MPE remain unverified; enumeration constants alone do not prove support |
| Regions | Playlist add/remove/split, Region setters/trim, AudioRegion fade setters, scale amplitude | Nondestructive editing with StatefulDiffCommand; handle source/playlist ownership |
| Crossfade | AudioPlaylist and fade primitives | Dedicated precise crossfade API not verified; do not simulate it as two fades |
| Stretch/shift | LuaAPI Rubberband helper | Offline helper exists; heavy work must not be added to 100ms polling callback without job isolation |
| Plugins | LuaAPI list_plugins/new_plugin, Route add/remove/reorder, Plugin nth_parameter/get_parameter_descriptor, presets | Generic formats from inventory; no brand dependency; plugin indices and parameter port IDs differ |
| Parameter units | ParameterDescriptor lower/upper/normal/print_fmt exposed; C++ `unit`/symbol not fully bound | Report native/plugin units when unknown; never infer Hz from parameter name or invent a normalized mapping |
| Automation | control alist, ControlList add/events/clear, freeze/thaw, memento_command | Batch points, explicit time domain and native units; grouped native undo possible |
| Timeline | TempoMap read/write_copy/update/abort_update, BBT/sample/quarter conversion | Respect real tempo/meter maps; pair every write_copy with update or abort |
| Markers | Locations list/add_range/remove; Location setters | Range creation exposed; mark constructor/flags creation needs care |
| Groups | Session new/add/remove group, RouteGroup bindings | Source-backed group operations; property surface depends on bindings |
| Sends | Session add_internal_send, Send amp, InternalSend target_route | Stable processor IDs; prohibit feedback cycles without explicit supported design |
| Routing | PortManager get_ports/get_connections/connect/disconnect; IO ports | Validate direction, data type, loop/feedback policy and backend port names |
| Undo | HistoryOwner begin/commit/abort/add_command, Editor undo/redo | Abort discards command bookkeeping, **does not roll back effects**; ordinary route/control edits are not automatically undo commands |
| Session | save_state/snap_name/path; dirty/writable; Session metadata not wholly exposed | Snapshot/save supported; unsafe session replacement cannot be hidden behind an action |
| Recording | rec controls, record_status, maybe_enable_record, disable_record, request_roll/stop, monitoring controls | Transport requests are asynchronous; inspect subsequent state, guard heavy edits while recording |
| Metering | PeakMeter meter_level, OSC meter feedback | Read meter data without audio processing in Python/GUI |
| Export | Session simple_export; SimpleExport preset/folder/name/range/check_outputs/run_export | Master export through actual Ardour preset, no invented format setters; run_export pumps GTK events and must be reentrancy guarded; stems are not directly exposed here |
| Audio import | Editor do_import with enumerated import mode/disposition/SRC quality | Source backed but many arguments/selection implications; enable only after actual verification |

Ardour LuaSession is an official standalone engine/session scripting program. It uses Dummy backend and common/non_rt bindings, provides create_session/load_session but no GUI Editor, and does not control the already running GUI instance. Useful for API integration tests and offline development, not a transparent live bridge replacement.

## Existing Ardour MCP assessment

[raibid-entertainment/ardour-mcp](https://github.com/raibid-entertainment/ardour-mcp), MIT; latest inspected commit 2025-11-20. Python + python-osc, low-level MCP, numeric strip addressing, mutable cached Session/Track state, feedback handlers and category tool classes. Tests include Mock/AsyncMock state/OSC integration: these do not establish actual DAW behavior. Roadmap completion statements and code differ; advertised create/marker/automation endpoints need source verification. Dependency `mcp>=0.1.0` has no compatible-major ceiling. Installation/client docs assume older SDK and environment paths. MIDI roadmap relies on a separate MIDI generation/import pipeline, not internal model editing.

| Existing capability | Quality/limitation observed | Decision |
|---|---|---|
| Transport | Useful OSC mapping, asynchronous send result | Reimplement; explicitly report unacknowledged OSC mutation |
| Mixer/recording | Category separation, familiar names; numeric indices/pan conversion need audit | Preserve concept, use stable ID Lua resolution |
| Feedback cache | RLock and callbacks; no full freshness/revision guarantee | Reimplement freshness and avoid treating partial cache as complete |
| Tracks/session | Some tools send assumed OSC addresses/actions | Use actual Lua APIs, validate on real runtime |
| Metering | Useful feedback idea; mock tests | Reimplement bounded received-state observation |
| Automation | Mode tools; no verified dense internal curves | Native Lua curves and memento undo |
| MIDI | External pipeline, deep editing missing | Internal model diff batches |
| Plugins/routing/editing/export | Deep generic features missing or roadmap | New adapter and capability manifest |
| Transactions/security | No robust cross-process uncertain-outcome model | Original guarded mailbox, fail-closed state, typed errors |
| Installer/platform | pip package and client examples; no proof on each OS | Native pathlib/platform discovery + CI; external DAW tests still needed |

Clean-room architectural replacement is superior to extending an OSC-only numeric-state design. No source code reused; aliases only when semantics are equivalent, no claim of drop-in compatibility.

## REAPER reference review

All four requested repositories were cloned, read and pinned in the source manifest. README claims were checked against bridge/client/tool/test code. None is a dependency.

* [xDarkzx/Reaper-MCP](https://github.com/xDarkzx/Reaper-MCP), Apache-2.0: file bridge, static Lua dispatch, heartbeat, token-conscious summaries and batch composition; large flat script and stylistic mixing presets are not appropriate for neutral primitives. Read Lua JSON/dispatch and client/tests.
* [ericjsolis/reaper-mcp](https://github.com/ericjsolis/reaper-mcp), Apache-2.0: similar file bridge lineage, tool profiles and MIDI batching; simplistic fixed slots require serialization and late reply handling. Read client, tools and Lua source; do not inherit REAPER time units/indices.
* [TwelveTake-Studios/reaper-mcp](https://github.com/TwelveTake-Studios/reaper-mcp), MIT: mailbox slot ownership, request IDs, orphan sweep, render-specific timeouts, install backups and tested named undo. Read tests for call_timeout/slot_claim/bridge_undo/render and bridge. REAPER defer/Undo APIs do not exist as Ardour equivalents.
* [danishaft/reaper-mcp](https://github.com/danishaft/reaper-mcp), MIT: layered services, default-deny media roots, capability profiles, preflight, bridge error envelopes; explicitly returns OUTCOME_UNCERTAIN after a published mutation timeout. Adopt that principle independently. Its large provider/tuning/profile layer would add unnecessary coupling.

Other search results include bonfire-systems/reaper-mcp; no additional implementation is incorporated. Chosen references already cover IPC, batching, undo, safety and production workflow patterns. Maintenance dates are repository observations, not assurances of support.

## Other audio MCP projects and reuse

* [ZipseLu/lmms-mcp](https://github.com/ZipseLu/lmms-mcp), MIT: edits LMMS project XML, patterns/notes/effects; useful explicit ticks and inspection. Offline XML editing of an open Ardour session is unsafe, so rejected as live architecture.
* [xDarkzx/Audacity-MCP](https://github.com/xDarkzx/Audacity-MCP), Apache-2.0: real mod-script-pipe on Audacity 3, late reply draining and long effect jobs. Explicitly documents Audacity 4 interface removal; reinforces runtime capabilities. No Audacity dependency.
* [tubone24/midi-mcp-server](https://github.com/tubone24/midi-mcp-server), MIT: TypeScript/MIDI files; good schema examples, not internal Ardour editing. No reuse.
* [JuzzyDee/audio-analyzer-rs](https://github.com/JuzzyDee/audio-analyzer-rs), MIT: offline structured spectral/loudness/stereo analysis, compact comparisons. DSP claims in its README are not independent validation. Avoid introducing Rust build stack; use mature optional scientific Python libraries with numerical fixture tests.

No neural/cloud audio generation dependency. No subjective quality score or unvalidated pitch/tempo estimator enabled. NumPy/SciPy + libsndfile/SoundFile + pyloudnorm are suitable optional offline analysis components; standard library cannot reliably replace these algorithms/codecs at reasonable maintenance cost. True peak must be labelled an oversampled estimate unless validated to a BS.1770 reference suite.

## Comparison matrix

Legend: Native = source exposes operation; Partial = narrower or weaker semantics; Missing = absent; Planned = architecture supports future adapter, not implemented claim. Ultra implementation status is separately maintained.

| Feature | Native OSC | Ardour Lua | Existing Ardour MCP | Strong REAPER references | Ultra design |
|---|---|---|---|---|---|
| Transport/record | Native | Native | Present | Present | Both, explicit confirmation limits |
| Mixer/metering | Native | Native | Present/cache | Present | Stable IDs + inspected values |
| Session save/snapshot | Actions | Native | Partial | Present | Defined Lua commands |
| Stable objects | Strip indices | Native IDs | Missing | GUID/adapters | Ardour IDs, guarded note refs |
| MIDI regions/notes | Missing | Native Editor/model | External MIDI pipeline | Native/batches | Internal model, dense batches |
| CC/bend/SysEx/MPE | Missing editing | Partial | Missing | Partial/native | Capability-gated, no invented support |
| Plugins/presets | Existing instance only | Native | Partial/missing | Present | Generic inventory/native values |
| Sends/ports/groups | Existing sends | Native | Partial | Present | Native IDs and bounded commands |
| Region trim/split/fades | Missing | Native | Missing | Present | Native nondestructive editing |
| Stretch/pitch | Missing | Offline helper | Missing | Present | Deferred until safe jobs verified |
| Automation curves | Mode only | Native | Partial | Present | Batch native undo |
| Tempo/meter/conversion | Partial | Native | Partial | Present | Actual TempoMap |
| Export/stems | Actions | Preset master/partial | Missing | Present | Preset master; no fake stems |
| Local analysis | Missing | Heavy helpers | Missing | Present | Optional worker-thread analysis |
| Transaction rollback | Missing | Command bookkeeping | Missing | Native undo wrappers | Limited, explicit guarantees |
| Preflight/concurrency | Missing | Build on readback | Missing | Partial/strong | Guarded preflight, scope-labelled revision |
| Health/security/IPC | UDP only | Hook/file primitives | Basic | Heartbeat/default deny | Private mailbox, correlation, uncertainty |
| MCP/resources | N/A | N/A | Older SDK | Various | Official stable v2 + STDIO |
| Cross-platform proof | Ardour portable | Ardour portable | Assumptions | CI varying | Pure Python matrix; DAW proof separate |

## Client configuration evidence

[Codex MCP documentation](https://developers.openai.com/codex/mcp/) was fetched successfully on 2026-10-02 (redirect to learn.chatgpt.com/docs/extend/mcp?surface=cli); `[mcp_servers.NAME]` TOML and STDIO command/args are supported. [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) were fetched successfully and show `claude mcp add`, project `.mcp.json` with `mcpServers`, and STDIO transport. [Official local-server guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers) redirects to the current 2026-07-28 guide and confirms Claude Desktop JSON, macOS `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows `%APPDATA%\\Claude\\claude_desktop_config.json`. Client applications themselves were not installed/launched; schemas/snippets and the official SDK client are tested, application E2E remains external. Configuration generation prints snippets and never changes an existing client file.

## Runtime corrections

Real 8.12 integration proved that route/processor/playlist/region IDs require `to_stateful():id():to_s()`, IO `n_ports()` returns ChanCount (`n_total()`), Send has `gain_control()` (no `amp()` binding), `RouteGroup()` is not a valid constructor in that build, and `Session:maybe_enable_record()` returns void. `is_singleton()` is absent from 9.8 bindings too; use available master/monitor/auditioner/surround flags. The 8.12 Editor lacks MidiTimeAxisView creation bindings; 9.8 explicitly registers them. Existing-region MIDI model editing uses a separate API and must be validated independently. Default Dummy backend is hidden in release GUI builds; the disposable integration harness opts in and suppresses only its own saved memory-warning preference, without GUI input automation.
