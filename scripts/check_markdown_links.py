"""Validate local links in repository Markdown files."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {".git", ".venv", "site", "__pycache__"}
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not IGNORED_DIRS.intersection(path.relative_to(ROOT).parts)
    )


def link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    return re.split(r"\s+[\"']", target, maxsplit=1)[0]


def main() -> int:
    checked_links = 0
    failures: list[str] = []

    for source in markdown_files():
        content = source.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(content):
            target = link_target(match.group(1))
            parsed = urlparse(target)
            if not target or target.startswith("#") or parsed.scheme:
                continue

            checked_links += 1
            relative_target = unquote(target.split("#", maxsplit=1)[0])
            destination = (source.parent / relative_target).resolve()
            if not destination.exists():
                source_name = source.relative_to(ROOT)
                failures.append(f"{source_name}: {target}")

    if failures:
        print("Broken local Markdown links:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Checked {checked_links} local Markdown links: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
