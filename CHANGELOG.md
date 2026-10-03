# Changelog

## Unreleased

Fix Windows static checks by guarding native locking and ownership APIs with `sys.platform`. Upgrade CI runner packaging tools to patched setuptools before dependency audits, retaining all platforms, Python versions and security checks.

## 0.1.0 — development release, 2026-10-02

Original official MCP SDK v2 server, typed production primitives, allowlisted Ardour Lua EditorHook/mailbox, optional OSC adapter, deterministic simulator, offline analysis, portable installer/configuration generation, validation harnesses and documentation. Platform and advanced API gaps remain explicit; this release does not certify the full requested production workflow.
