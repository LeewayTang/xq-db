#!/usr/bin/env python3
"""Report the current session's context usage.

The model prompt does not expose a context percentage. This script derives it
from Claude Code's session transcript and, when available, the claude-hud
context cache.

Usage:
  python3 scripts/context-usage.py [--window 1000000] [--json] [--cwd PATH]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path


def config_dir() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    if configured:
        return Path(configured)
    for name in (".tclaude", ".claude"):
        candidate = Path.home() / name
        if candidate.exists():
            return candidate
    return Path.home() / ".claude"


def project_slug(cwd: Path) -> str:
    # Claude Code names project transcript folders by replacing "/" and "_"
    # with "-".
    return str(cwd).replace("/", "-").replace("_", "-")


def find_transcript(cwd: Path) -> Path | None:
    project = config_dir() / "projects" / project_slug(cwd)
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if session:
        candidate = project / f"{session}.jsonl"
        if candidate.exists():
            return candidate
    candidates = sorted(
        project.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def last_usage(path: Path) -> dict | None:
    last = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("isSidechain"):
                continue
            message = row.get("message") or {}
            usage = message.get("usage")
            if usage:
                last = {"model": message.get("model"), "usage": usage}
    return last


def hud_cache() -> dict | None:
    pattern = str(
        config_dir() / "plugins" / "claude-hud" / "context-cache" / "*.json")
    files = glob.glob(pattern)
    if not files:
        return None
    newest = max(files, key=os.path.getmtime)
    try:
        return json.loads(Path(newest).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=1_000_000)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--cwd", default="")
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    transcript = find_transcript(cwd)
    if not transcript:
        print(f"no transcript found for {cwd}", file=sys.stderr)
        return 1

    entry = last_usage(transcript)
    if not entry:
        print(f"no usage found in {transcript}", file=sys.stderr)
        return 1

    usage = entry["usage"]
    input_tokens = int(usage.get("input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    cache_create = int(usage.get("cache_creation_input_tokens") or 0)
    output = int(usage.get("output_tokens") or 0)
    used = input_tokens + cache_read + cache_create + output
    percent = round(used / args.window * 100, 2)
    hud = hud_cache()

    result = {
        "transcript": str(transcript),
        "session": transcript.stem,
        "model": entry.get("model"),
        "tokens": {
            "input": input_tokens,
            "cache_read": cache_read,
            "cache_creation": cache_create,
            "output": output,
            "used": used,
            "window": args.window,
        },
        "percent": percent,
        "hud": {
            "used_percentage": hud.get("used_percentage"),
            "context_window_size": hud.get("context_window_size"),
            "saved_at": hud.get("saved_at"),
        }
        if hud
        else None,
    }

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"transcript : {transcript}")
    print(f"model      : {entry.get('model')}")
    print(
        "tokens     : "
        f"input={input_tokens} cache_read={cache_read} "
        f"cache_create={cache_create} output={output}"
    )
    print(f"used       : {used:,} / {args.window:,} = {percent}%")
    if hud:
        print(
            "hud cache  : {}% used (window={}, saved_at={})".format(
                hud.get("used_percentage"),
                hud.get("context_window_size"),
                hud.get("saved_at"),
            )
        )
    print("note       : <total_tokens> in the system prompt is a budget, "
          "not context usage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
