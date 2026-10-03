# Changelog

## Unreleased

Simplify onboarding with a five-step README, full English/German installation guides, separate MCP client setup, updates/uninstall instructions and a documentation index. Verify direct GitHub ZIP installation with uv; Git is no longer needed for the recommended route. Add readable default CLI guidance while keeping `--json` diagnostics and raw client snippets stable. Correct the Ardour 9.8 script-manager menu and remove the unverified sandbox-preferences instruction. Check local documentation links in CI and add package repository metadata.

CLI automation should explicitly pass `--json`: install/uninstall/doctor/status/capabilities/test-connection now default to readable text. MCP STDIO output and configure snippets retain their existing formats.

Fix Windows static checks by guarding native locking and ownership APIs with `sys.platform`. Upgrade CI runner packaging tools to patched setuptools before dependency audits, retaining all platforms, Python versions and security checks.

Publish installer scripts as exact UTF-8 bytes so Windows newline conversion cannot invalidate uninstall checksums. Align Lua protocol test clients with the real mailbox's consumed-response cleanup and unique correlation IDs; add Windows rename and text-translation regression coverage.

## 0.1.0 — development release, 2026-10-02

Original official MCP SDK v2 server, typed production primitives, allowlisted Ardour Lua EditorHook/mailbox, optional OSC adapter, deterministic simulator, offline analysis, portable installer/configuration generation, validation harnesses and documentation. Platform and advanced API gaps remain explicit; this release does not certify the full requested production workflow.
