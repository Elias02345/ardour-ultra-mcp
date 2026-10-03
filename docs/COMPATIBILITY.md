# Compatibility

Native evidence date: 2026-10-02; hosted Python/MCP evidence date: 2026-10-03. This is development release 0.1.0, not a claim of complete production or cross-platform DAW certification.

| Environment | Evidence | Status |
|---|---|---|
| Linux x86_64, Debian 13, Python 3.12.14 | Pure Python/MCP/security/analysis tests; extracted Debian Ardour 8.12 common/non_rt LuaSession checks | Tested subset |
| Linux x86_64, Debian sid container, Python 3.14.8, Ardour 9.8.0~ds | Real EditorHook on Xvfb/Dummy engine, internal MIDI and export/analysis; standalone common bindings | Tested subset; consult TESTING.md for final counts |
| Other Linux distributions, JACK/PipeWire/ALSA hardware, ARM Linux | Portable source/path handling and CI recipes; no actual execution here | Requires external verification |
| macOS / Apple Silicon DAW target | Hosted macos-latest Python/MCP suites passed on Python 3.11–3.14; source-backed paths | Native Ardour/Apple Silicon DAW integration remains unverified |
| Windows / Windows 11 DAW target | Hosted windows-latest Python/MCP suites passed on Python 3.11–3.14, including locking and installer fixtures | Native Windows 11 Ardour, DACL protection and heartbeat replacement remain unverified |
| Python 3.11/3.13 | Hosted suite on all three OS runners; 3.11.16 also tested locally | Python/MCP layer tested; no inference about DAW support |
| Python 3.12/3.14 | Local Linux suites and hosted suite on all three OS runners | Python/MCP layer tested; no inference about DAW support |

See TESTING.md and artifacts/ci-validation.json for the successful 12-job matrix. Hosted OS labels do not certify a specific desktop OS/hardware combination. Lua protocol fixtures run in Lupa; they do not load native Ardour on macOS or Windows. The optional hosted Linux Ardour job was not run during this push.

Ardour 9.8 is the researched stable release. Current development master was inspected but not used for the production adapter. Supported commands are runtime-discovered from the running reviewed hook. Do not assume a new major is compatible. Official/repackaged builds may expose different bindings/plugins. Package metadata does not make all Ardour features available.

## Observed differences

* 8.12 RouteGroup parameters accept a raw nil pointer. 9.8 requires a typed empty `ARDOUR.RouteGroup()`; passing nil can crash native code. The bridge detects the constructor.
* 9.8 binds MidiTimeAxisView/add_region. The tested 8.12 build does not: create_midi_region is excluded. Existing-region note diffs are separately bound but were not exercised on an 8.12 editor fixture.
* 9.8 exposes Session UUID. Where it is absent, the session identifier is explicitly nonpersistent and scoped to the bridge/session epoch.
* 8.12 lacks Session:add_route_group. Group mutation commands are excluded; 9.8 group operations were tested. Ordinary groups are automatically removed when their last member leaves. The bound remove_route_group cannot remove an empty group; calls fail explicitly.
* Native Location:id returned `0` in a 9.8 standalone probe despite different objects. Marker mutation is disabled until reliable identity/casting and undo are verified.
* Ardour supports conditional plugin formats. Only actual installed formats belong in inventory. Linux LV2 effects and the bundled ACE Reasonable Synth were exercised; VST3/VST2/AudioUnit and other hosts remain external.

The GUI harness uses the actual 9.8 binary, installed libraries/plugins and a source-matched Lua signal table. It never synthesizes mouse/keyboard input. Dummy engine testing proves binding behavior and offline rendering, not hardware recording, low-latency stability or unattended real-world sessions. Explicit Windows DACL verification, existing-target heartbeat rename behavior, and Unicode Lua fopen/rename behavior need native tests before advertising Windows DAW support.

The official MCP SDK 2.3.0 negotiates 2026-07-28 and older supported protocol revisions. Actual subprocess STDIO is tested with the official Client. Claude Desktop/Code and Codex configuration formats were checked against current official docs; those applications were not launched here.

Native OSC transport queries were exercised on 9.8. A locate request did not move the Dummy fixture playhead through either this codec or liblo's sender, while explicit Lua locate worked. OSC readback also remained at zero after a verified Lua locate. OSC queries report reply_received but confirmed=false/state_verified=false; mutation submission is experimental/unacknowledged. The root cause is unverified, and no deterministic OSC execution or state claim is made. The probe is preserved in artifacts/osc-transport-probe.json.
