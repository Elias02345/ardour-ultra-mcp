"""Check repository-local Markdown file links without network access."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def broken_links(root: Path) -> list[str]:
    failures = []
    documents = sorted([*root.glob("*.md"), *(root / "docs").rglob("*.md")])
    for document in documents:
        content = document.read_text(encoding="utf-8")
        for match in re.finditer(r"\[[^\]\n]*\]\(([^)\n]+)\)", content):
            destination = match.group(1).split(' "', 1)[0].strip("<>")
            url = urlsplit(destination)
            if url.scheme or url.netloc or not url.path:
                continue
            target = document.parent / unquote(url.path)
            if not target.exists():
                line = content[: match.start()].count("\n") + 1
                failures.append(f"{document.relative_to(root)}:{line}: missing {destination}")
    return failures


if __name__ == "__main__":
    errors = broken_links(ROOT)
    for error in errors:
        print(error)
    if not errors:
        print("Local Markdown file links passed.")
    raise SystemExit(bool(errors))
