# Contributing

Read [development](docs/DEVELOPMENT.md), [security](docs/SECURITY.md), and [compatibility](docs/COMPATIBILITY.md). Submit source evidence with every new Ardour command. A method name in a C++ header is insufficient: verify its registered Lua/OSC binding and execute it where possible. Keep unsupported operations honest in capabilities and status.

Use typed requests, explicit units, stable Ardour IDs, bounded payloads, non-realtime hook execution, preflight, and useful readback. Never add arbitrary code execution or shell tools. Test failures and ambiguous mutation outcomes, not only happy paths. Do not describe simulator tests as Ardour integration. New files are GPL-3.0-or-later unless clearly marked third-party.

Run the checks in TESTING.md; regenerate the tool reference. Platform maintainers should submit real DAW E2E artifacts with version, architecture, backend and plugin formats. Respect contributor privacy: no user sessions/audio or tokens in fixtures and logs.
