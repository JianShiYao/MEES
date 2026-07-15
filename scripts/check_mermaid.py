#!/usr/bin/env python3
"""Render every Mermaid fence and report the exact Markdown source on failure."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FENCE_RE = re.compile(r"^\s*```mermaid\s*$\n(.*?)^\s*```\s*$", re.MULTILINE | re.DOTALL)
PINNED_PACKAGE = "@mermaid-js/mermaid-cli@11.12.0"


def markdown_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "*.md"], cwd=ROOT,
        capture_output=True, check=True,
    )
    names = result.stdout.decode("utf-8").split("\0")
    return [ROOT / name for name in names if name]


def diagrams(files: list[Path]) -> list[dict]:
    found = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for index, match in enumerate(FENCE_RE.finditer(text), start=1):
            found.append({
                "source": path.relative_to(ROOT).as_posix(),
                "line": text.count("\n", 0, match.start()) + 1,
                "index": index,
                "body": match.group(1).strip() + "\n",
            })
    return found


def renderer_command(allow_npx: bool) -> tuple[list[str], str]:
    configured = os.environ.get("MERMAID_CLI")
    if configured:
        return [configured], configured
    executable = shutil.which("mmdc") or shutil.which("mmdc.cmd")
    if executable:
        return [executable], executable
    if allow_npx:
        cache_roots = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "npm-cache" / "_npx",
            Path.home() / ".npm" / "_npx",
        ]
        for cache_root in cache_roots:
            if not cache_root.is_dir():
                continue
            for package_json in cache_root.glob("*/node_modules/@mermaid-js/mermaid-cli/package.json"):
                try:
                    version = json.loads(package_json.read_text(encoding="utf-8")).get("version")
                except (OSError, json.JSONDecodeError):
                    continue
                if version != "11.12.0":
                    continue
                binary = package_json.parents[2] / ".bin" / ("mmdc.cmd" if os.name == "nt" else "mmdc")
                if binary.is_file():
                    return [str(binary)], f"cached {PINNED_PACKAGE}"
        npx = shutil.which("npx.cmd") or shutil.which("npx")
        if npx:
            return [npx, "--yes", PINNED_PACKAGE], f"npx {PINNED_PACKAGE}"
    raise RuntimeError(
        "Mermaid CLI unavailable; install @mermaid-js/mermaid-cli@11.12.0 "
        "or rerun with --allow-npx"
    )


def browser_config(outdir: Path) -> Path | None:
    candidates = [
        os.environ.get("PUPPETEER_EXECUTABLE_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    ]
    executable = next((item for item in candidates if item and Path(item).is_file()), None)
    if not executable:
        return None
    config = outdir / "puppeteer.json"
    config.write_text(json.dumps({
        "executablePath": executable,
        "args": ["--no-sandbox", "--disable-setuid-sandbox"],
    }, indent=2), encoding="utf-8")
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Render tracked and unignored Mermaid fences")
    parser.add_argument("--outdir", default="build/mermaid")
    parser.add_argument("--json", default="build/mermaid/report.json")
    parser.add_argument("--allow-npx", action="store_true")
    args = parser.parse_args()

    try:
        items = diagrams(markdown_files())
        command, renderer = renderer_command(args.allow_npx)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        print(f"[tool] {exc}", file=sys.stderr)
        return 2

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    puppeteer_config = browser_config(outdir)
    failures = []
    for sequence, item in enumerate(items, start=1):
        source = outdir / f"diagram-{sequence:03d}.mmd"
        target = outdir / f"diagram-{sequence:03d}.svg"
        source.write_text(item["body"], encoding="utf-8")
        render_command = command + ["-i", str(source), "-o", str(target), "-b", "transparent"]
        if puppeteer_config:
            render_command += ["-p", str(puppeteer_config)]
        result = subprocess.run(
            render_command,
            cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            capture_output=True,
        )
        if result.returncode:
            failures.append({
                "source": item["source"], "line": item["line"],
                "index": item["index"], "message": (result.stderr or result.stdout).strip(),
            })

    report = {
        "tool": "check_mermaid", "renderer": renderer,
        "diagram_count": len(items), "failure_count": len(failures),
        "failures": failures,
    }
    report_path = ROOT / args.json
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for failure in failures:
        print(f"{failure['source']}:{failure['line']}: {failure['message']}")
    print(f"Mermaid: {len(items)} diagram(s), {len(failures)} failure(s); {args.json}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
