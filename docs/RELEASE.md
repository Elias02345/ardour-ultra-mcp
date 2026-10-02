# Release preparation

0.1.0 is a development release. Package artifacts can be built locally; no PyPI publication, public Git remote, GitHub release, client marketplace entry or complete production certification is claimed.

Before release, run all local checks in TESTING.md, build wheel/sdist, install the wheel in a clean environment and run official-client STDIO tests. Confirm the wheel includes the Lua template and license. Run real Ardour editor E2E on each advertised OS/architecture/version, validate optional plugin formats and export fixtures, and review known gaps. Do not infer DAW support from pure Python CI.

GitHub CI tests Python 3.11..3.14 on Ubuntu/macOS/Windows; workflows are supplied but their hosted runs have not executed in this local session. The optional workflow_dispatch Linux integration installs distribution Ardour, which can be older than the researched stable release. Record exact runtime versions. Full macOS/Windows Ardour binary distribution/install in CI may need platform-specific source builds or user-provided binaries; licensing of individual plugins must be respected. Ardour GPL permits redistribution under its conditions; do not invent a legal prohibition.

Tag-triggered release workflow builds downloadable artifacts only. PyPI trusted publishing is deliberately not configured without a real repository/maintainer identity. Publish only after the maintainer reviews the concrete built distribution and evidence. Keep semantic versions/dependency major limits, CHANGELOG, dependency notices and capability protocol compatibility aligned. Dependabot monitors Python and GitHub Actions monthly.
