# Security and threat model

The trust boundary is an MCP client/agent requesting allowlisted musical operations against a local user-owned Ardour session. Protect other sessions/files, prevent accidental destructive operations, reject stale object selection and bound work. A malicious process already running as the same OS user can alter Ardour, script files or the mailbox; this is not a sandbox against that process.

STDIO is the default and exposes no listening service. Lua IPC uses a private per-user directory (0700 checked on POSIX), protocol/version checks, a private random nonce, request correlation, bridge epoch, deadline, message size/depth/count limits, strict JSON, canonical native object IDs before PBD construction, and an operation allowlist. No execute_arbitrary_lua, eval, general shell tool, or filesystem browsing tool exists. Lua's incoming protocol never loads code. Ardour itself persists trusted script bytecode; the test harness uses that official format only for reviewed installed code, outside MCP input.

Python rejects symlink IPC files with O_NOFOLLOW where supported, atomically publishes bounded payloads and locks the request slot across clients. POSIX ownership/mode is checked. Windows uses the user's local app-data directory and msvcrt locking, but explicit DACL verification/hardening is not yet implemented. Full Windows DAW/locking E2E is external. Lua cannot independently reproduce every POSIX ownership/DACL or symlink race check; defend the mailbox as an OS-user private directory.

Only explicit resolved media/export roots are accepted. Paths must be absolute; traversal/symlink escapes are rejected. Exports use a fresh exclusively created child directory and cannot overwrite existing files. Bridge rechecks installed lexical export root boundaries; same-user filesystem races remain outside the security boundary. Session save intentionally writes the current session; snapshots refuse existing names. No project open/create tool can silently replace active work. Install backs up changed files; uninstall refuses modified scripts.

Dry-run validates targets before mutation; deletes/removal/clear/replace require confirm_delete. Expected revisions reject known observed changes but do not guarantee complete human-edit exclusion. MIDI references validate the exact model. No distributed locks against a human editing in Ardour and no ACID transactions are promised. Published mutation timeout/failure with uncertain state is surfaced as OUTCOME_UNCERTAIN; do not auto-retry. Reconcile actual state and mailbox before continuing.

IPC/JSON/editing runs only in the EditorHook's GUI context. Never install it as DSP or Session realtime callback. Batches are bounded and mutations are blocked while actively recording (except stop). Heavy export may block the UI and exceed heartbeat freshness; real-time audio-thread profiling/conformance is a remaining gap. Offline analysis is never run in Ardour.

Native OSC is optional. Python binds loopback and rejects non-loopback peers. Ardour's own liblo service can bind beyond loopback; enabling native OSC requires host firewall/local access control. Composite does not need OSC for editing.

Diagnostics go to stderr and do not include the private nonce. Native binding errors can include internal script paths to aid diagnosis; user audio and session contents should not be attached to public issues. Security scans and test evidence are in TESTING.md. Dependency audit with no known vulnerabilities is point-in-time evidence, not a guarantee.

Report vulnerabilities privately to the repository maintainer once a public repository/contact exists; no invented reporting address is provided in this local project.
