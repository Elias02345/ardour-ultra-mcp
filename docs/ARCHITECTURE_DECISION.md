# ADR 001: Lua-authoritative mailbox with optional experimental OSC

Accepted 2026-10-02 after source inspection and transport prototypes.

A: Native OSC has the lowest overhead, no bridge install and native feedback. It cannot address persistent IDs or edit MIDI/regions; UDP sends do not acknowledge execution. Reject as the only backend.

B: A private file mailbox is usable in non-realtime Ardour Lua because `io`/`os` remain available while `require`/LuaSocket are removed. An EditorHook processes at most one bounded request per 100ms tick. It can resolve persistent Ardour objects and return correlated results. Costs: UI latency, manual hook activation and incomplete transactional APIs. Prefer this for verified deep editing. Never use DSP/Session realtime callbacks for IPC.

C: Use a composite adapter: the Lua backend owns precise stable-ID operations; optional native OSC exposes received replies and explicitly unacknowledged transport operations. The adapters never silently replace a missing deep command with an index-based action. Capability discovery describes each backend independently. OSC is optional so the standard installation can avoid Ardour's non-loopback OSC exposure entirely.

The standalone official LuaSession program is an additional integration harness/offline interface. It is not the already running GUI session and lacks Editor operations. No modification of Ardour's C++ source, no REAPER dependency, no arbitrary Lua tool.

## Measurements

[architecture-prototype.json](../artifacts/architecture-prototype.json) records synthetic UDP echo and fixed-mailbox timing with a 100ms consumer period. This measures transport overhead only, not live Ardour API execution. Dense MIDI and automation must be batched because 100ms per individual note is unacceptable. Real backend benchmarks are recorded separately when feasible; fake timings are labelled.

Real 9.8 Dummy runtime queries replied, but OSC locate did not move and OSC state differed from successful Lua locate readback. Liblo reproduced the behavior; root cause is unverified. OSC transport queries and mutations are experimental and state_verified=false; Lua is authoritative. The architecture retains OSC as an optional adapter for further verified telemetry work, not a deterministic fallback.

## Guarantees and limitations

* All STDIO output belongs to official MCP SDK; diagnostics to stderr.
* Typed requests validated before dispatch, allowlisted handlers validate again in Lua. No code evaluation, shell access or filesystem browser.
* Private per-user mailbox; protocol version, nonce, request ID, bridge instance epoch, deadline; exclusive OS lock serializes multiple clients. Publish by atomic replace. Do not retry a timed-out mutation automatically.
* Stable route/region/playlist/processor/group IDs. MIDI references are model-scoped content references, not fictitious persistent note UUIDs.
* Native undo for model diffs/automation/region diffs; compensation for supported controls. Do not advertise general ACID or make `abort_reversible_command` mean rollback.
* Revision is scoped to observed state. If full human-edit coverage is not proven, report that limitation and use target fingerprints for MIDI edits.
* Expensive file analysis occurs on worker threads in Python, never the audio callback. Large edits may still occupy UI time; bound sizes and reject heavy changes during active recording.
* Export through Ardour's actual SimpleExport/preset surface only; no promised stems/format settings that are absent from binding. Use unique empty output directories for overwrite prevention.
