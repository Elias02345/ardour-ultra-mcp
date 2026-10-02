from __future__ import annotations

import os
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path


def config_directory(
    major: int = 9,
    *,
    system: str | None = None,
    home: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    system, home, env = (
        system or platform.system(),
        home or Path.home(),
        os.environ if env is None else env,
    )
    if system == "Darwin":
        return home / "Library" / "Preferences" / f"Ardour{major}"
    if system == "Windows":
        base = (
            env.get("XDG_CONFIG_HOME") or env.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        )
        return Path(base) / f"Ardour{major}"
    return Path(env.get("XDG_CONFIG_HOME", str(home / ".config"))) / f"ardour{major}"


def mailbox_directory(
    *, system: str | None = None, home: Path | None = None, env: Mapping[str, str] | None = None
) -> Path:
    system, home, env = (
        system or platform.system(),
        home or Path.home(),
        os.environ if env is None else env,
    )
    if system == "Darwin":
        return home / "Library" / "Application Support" / "ardour-ultra-mcp"
    if system == "Windows":
        return Path(env.get("LOCALAPPDATA", str(home / "AppData" / "Local"))) / "ardour-ultra-mcp"
    return Path(env.get("XDG_STATE_HOME", str(home / ".local" / "state"))) / "ardour-ultra-mcp"


def find_ardour() -> list[str]:
    found = []
    for name in ["ardour", "ardour9", "ardour8", "Ardour.exe", "ardour.exe"]:
        path = shutil.which(name)
        if path and path not in found:
            found.append(path)
    if platform.system() == "Darwin":
        for base in [Path("/Applications"), Path.home() / "Applications"]:
            if base.is_dir():
                found.extend(str(p) for p in base.glob("Ardour*.app/Contents/MacOS/Ardour*"))
    if platform.system() == "Windows":
        for key in ["ProgramFiles", "ProgramFiles(x86)"]:
            program_base = os.environ.get(key)
            if program_base:
                found.extend(str(p) for p in Path(program_base).glob("Ardour*/bin/Ardour.exe"))
    return found


def detect_versions(
    candidates: list[str] | None = None,
) -> list[dict[str, str | int | bool | None]]:
    """Run only discovered Ardour binaries with their official version flag."""
    import re

    # Fixed version probe of OS-discovered Ardour, not an MCP command or shell.
    import subprocess  # nosec B404

    results: list[dict[str, str | int | bool | None]] = []
    for executable in (find_ardour() if candidates is None else candidates)[:8]:
        try:
            completed = subprocess.run(  # nosec B603
                [executable, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                check=False,
            )
            match = re.search(r"Ardour\s*(\d+)\.(\d+)(?:\.(\d+))?", completed.stdout, re.I)
            results.append(
                {
                    "executable": executable,
                    "verified": bool(match),
                    "version": match.group(0) if match else None,
                    "major": int(match.group(1)) if match else None,
                }
            )
        except (OSError, subprocess.TimeoutExpired):
            results.append(
                {"executable": executable, "verified": False, "version": None, "major": None}
            )
    return results
