# Final gap analysis

0.1.0 is a working, tested development implementation with real Linux Ardour integration. It does **not** meet every requested production-grade definition-of-done condition. Missing adapters are not automatically Ardour limitations. The distinctions below are intentional; unavailable commands return structured errors and capability discovery describes their absence.

## Comparison with the brief and native Ardour

| Area | Delivered | Remaining / reason |
|---|---|---|
| MCP | Official stable SDK v2, STDIO, typed requests/structured results, 7 resources, 1 prompt, progress for analysis/export | Optional transports, resource subscriptions/event notifications, tested branded client applications |
| Layering/state | Protocol-independent catalog/service/backend; split simulator editing/plugin/group modules; explicit refreshed reads | Fully typed canonical object graph, comprehensive event cache, per-domain production services and selective fields/time-range reads |
| Health | Correlated bridge epoch/heartbeat, experimental OSC replies, session/engine observations, doctor/runtime/version checks | Complete independent process discovery and continuous synchronization health; busy UI can delay heartbeat |
| Session | Info, stable UUID when bound, save and safe named snapshots | List/load snapshots, metadata, save-as, safe live create/open; replacement lifecycle adapter not verified |
| Undo/transactions | Native note/region/automation commands; compensated control batch; simulator atomic snapshots | General begin/commit ACID, one native undo for arbitrary control batches, undo-history introspection; native abort does not reverse effects |
| Transport/recording | Play/stop/typed locate, loop update/disable, arm/monitor, record start/stop | Pause/speed helpers, creation of loop/punch locations, punch options, hardware recording validation; async requests need readback |
| Timeline | Typed BBT/seconds/samples/quarter ticks; native TempoMap conversion; constant tempo/meter insertion | Full tempo/meter enumeration, ramp controls/removal, timecode/drop-frame offsets; grid/enumeration bindings differ |
| Tracks/buses/groups | Audio/MIDI/bus creation; IDs, name, gain/pan/mute/solo/delete; 9.8 groups/properties/membership | Track clone/reorder/color/input/output APIs, group rename/subgroups/master linkage; empty-group removal binding limitation |
| MIDI | Internal region creation in 9.8, note list/insert/edit/delete batches, guarded references, independent region copy, region move/trim/split | CC/bend/pressure/aftertouch/program/SysEx/MPE adapters, merge, musical-position note convenience, quantize/humanize/theory helpers; persistence/construction semantics need validation |
| MIDI identity | Exact model-scoped guarded references | Persistent note UUID unavailable in bound NotePtr; references expire and shared-source edits require inspection |
| Audio regions | List/get/move/trim/split/delete/copy/gain/mute/lock/fade-duration handlers | Import adapter, normalization/reverse, fade-shape/crossfade, transient/stretch/pitch asynchronous jobs; a real offline-created audio fixture verifies ordinary editing; import, additional formats/source ownership and all failure outcomes need broader native tests |
| Playlists/markers | Active playlist IDs/state through regions | Playlist switching/clone management; markers/ranges disabled after Location ID probe returned 0; no unsafe name-only mutation |
| Plugins | Runtime inventory/instruments, insertion/removal/enabled, stable processor ID, native descriptor/parameter batches, preset list/load | Rescan, reorder/copy, preset save/state export, parameter semantic profiles, physical unit/normalized mappings not fully bound; additional format tests |
| Routing | Internal sends/gain/removal, actual port inventory/connections, graph feedback checks | Send pan, route IO layout, complete internal raw routing, sidechain pin setup, additional workflow helpers; avoid audio feedback |
| Automation | Gain/pan/plugin/send lists, dense curves/replace/clear, linear/discrete modes with memento undo | All lane inventory, selective/range reads, point identities/move/delete helpers, bezier curves; 10,000-point read ceiling and native zero-anchor semantics |
| Mixer/meter | Exact native values, snapshot queries, momentary dBFS peak | Complete effective VCA/automation mixer graph, continuous subscribed meters, native clipping history |
| Export/analysis loop | Experimental SimpleExport master range/preset to new directory; returned file metadata; local analysis/compare | Stems, track/bus selection, format/rate/dither/normalization setters, export-preset enumeration, async job cancellation; SimpleExport is narrower than export manager |
| Local analysis | Peak/RMS/crest/LUFS/estimated true peak/spectrum/stereo/DC/silence/full-scale samples | Independent true-peak conformance suite, LRA/dynamic-range standard, transients/tempo/pitch; no subjective quality claims |
| Production workflows | Composable primitives, ensure_bus and render_and_analyze with workflow prompt | Tested sidechain/vocal/drum/parallel/master/gain-stage helpers and additional ensure_* helpers, complete 30-second soundtrack target E2E |
| Concurrency | Scoped observed revisions, exact MIDI guards, serialized cross-client mailbox | Complete human-edit generation including plugin/automation/ports/tempo, event-derived revisions, simultaneous shared-source workflow tests |
| Efficiency | Pagination for core lists, 10,000-note/point batches, bounded IPC; simulator benchmarks and real timings | Large real 100+ track/100k note sessions, cancellable UI jobs, further range/filter/field projection and plugin bounds profiling |
| Installation | Portable script/mailbox installation, backups, doctor/version selection, unmodified-file uninstall, printed client configs | Fully automatic hook activation deliberately omitted; post-install live check requires active hook; native macOS/Windows installation/privacy verification |
| Platforms | Linux subsets actually executed | macOS/Windows DAW proof, hardware/audio backends, Apple Silicon, Windows DACL/Unicode IPC, complete OS CI results |
| Quality/release | Meaningful tests, branch coverage, lint/types/security/dependency audit/build/clean wheel install, CI/release workflows, generated docs | Higher critical-path coverage, hosted CI, formal protocol conformance/realtime profiling, public repository/PyPI release and maintainer identity |

## Comparison with reviewed MCP peers

The existing Ardour MCP provides broader familiar OSC names/feedback patterns, but numeric strip addressing, partial cache and assumed/roadmap operations cannot establish deterministic internal MIDI editing. This implementation replaces those assumptions with persistent object resolution, exact model diffs, correlated local IPC and measured integration. It does not reproduce every legacy tool name; see MIGRATION.md.

The strongest reviewed REAPER designs cover additional MIDI/controller events, rendering/stems, sidechains, workflow profiles and mature installer tests. Ardour does not share REAPER defer/GUID/render/Undo APIs. Their safety, batching and uncertain-outcome ideas were reimplemented independently; claiming feature parity would be false. Source pins and the major-category comparison matrix are in RESEARCH.md.

## Next work in dependency order

1. Run the native editor harness on macOS Apple Silicon and Windows 11, harden/verify Windows mailbox DACL and file replacement, then set an evidence-based support matrix.
2. Expand audio-region fixtures and implement import with precise track insertion/resampling ownership, persistence/undo validation and exclusive output semantics.
3. Build safe asynchronous Ardour jobs and deeper export manager adapters before stems/stretch/pitch. Profile audio-thread/UI behavior with hardware backends.
4. Verify MIDI controller/program/event persistence and integrate batch edits, including shared/trimmed-source guards; add a better musical note addressing convenience layer.
5. Add typed canonical snapshots/events and target-specific concurrency for plugins/automation/ports/tempo; keep the current revision limitation visible.
6. Add deterministic sidechain/plugin pin workflows and ensure_* helpers only after atomic routing/processors can compensate correctly.
7. Raise meaningful critical-path coverage and run the supplied OS/Python hosted CI, then prepare a reviewed public development release.

The free/local/open-source/vendor-neutral properties are delivered. Complete cross-platform professional unattended production remains a development objective, not a verified release claim.
