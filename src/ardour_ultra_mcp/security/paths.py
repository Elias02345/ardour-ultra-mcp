"""Explicit source/export roots, no filesystem browsing and no silent overwrite."""

from __future__ import annotations

import os
from pathlib import Path

from ..models.base import DomainError, ErrorCode


class PathPolicy:
    def __init__(
        self, media_roots: tuple[Path, ...] = (), export_roots: tuple[Path, ...] = ()
    ) -> None:
        self.media_roots = tuple(p.expanduser().resolve() for p in media_roots)
        self.export_roots = tuple(p.expanduser().resolve() for p in export_roots)

    def _within(self, value: str, roots: tuple[Path, ...]) -> Path:
        if not value or any(ord(c) < 32 for c in value) or "://" in value:
            raise DomainError(
                ErrorCode.VALIDATION_ERROR, "Expected an explicit local absolute path."
            )
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise DomainError(ErrorCode.PERMISSION_DENIED, "Relative paths are not permitted.")
        resolved = path.resolve()
        if not any(resolved.is_relative_to(root) for root in roots):
            raise DomainError(
                ErrorCode.PERMISSION_DENIED,
                "Path is outside explicitly allowed roots.",
                "Start server with --media-root or --export-root for this project.",
            )
        return resolved

    def audio(self, value: str) -> Path:
        path = self._within(value, self.media_roots + self.export_roots)
        if not path.is_file():
            raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Audio file does not exist.")
        if path.suffix.casefold() not in {
            ".wav",
            ".wave",
            ".flac",
            ".aiff",
            ".aif",
            ".ogg",
            ".caf",
        }:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Unsupported analysis container.")
        return path

    def new_export_directory(self, value: str, *, dry_run: bool = False) -> Path:
        path = self._within(value, self.export_roots)
        if path.exists():
            raise DomainError(
                ErrorCode.FILE_EXISTS,
                "Export directory already exists.",
                "Use a new directory; existing files are never overwritten.",
            )
        if not path.parent.is_dir():
            raise DomainError(ErrorCode.OBJECT_NOT_FOUND, "Export parent directory does not exist.")
        if not dry_run:
            try:
                path.mkdir(mode=0o700)
            except FileExistsError as exc:
                raise DomainError(
                    ErrorCode.FILE_EXISTS, "Export directory was created concurrently."
                ) from exc
        return path


def private_directory(path: Path) -> Path:
    """Fail closed on a shared/symlink directory instead of changing another owner's mode."""
    if path.is_symlink():
        raise DomainError(ErrorCode.PERMISSION_DENIED, "Mailbox directory must not be a symlink.")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        st = path.stat()
        if st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise DomainError(
                ErrorCode.PERMISSION_DENIED,
                "Mailbox must be owned by current user with mode 0700.",
                "Choose a private mailbox or correct its permissions.",
            )
    return path.resolve()
