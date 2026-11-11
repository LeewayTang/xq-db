#!/usr/bin/env python3
"""Create, resolve and index handoff documents.

Usage:
  python3 scripts/handoff.py new <slug> [--trigger pre-compact|manual]
        [--next "one-line next action"] [--session ID] [--reason TEXT] [--dry-run]
  python3 scripts/handoff.py resolve [query]
  python3 scripts/handoff.py list
  python3 scripts/handoff.py rebuild-index
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFFS = ROOT / "docs" / "superpowers" / "handoffs"
LATEST = HANDOFFS / "HANDOFF-LATEST.md"
INDEX = HANDOFFS / "HANDOFFS.md"
TEMPLATE = HANDOFFS / "HANDOFF-TEMPLATE.md"


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def iso(value: dt.datetime) -> str:
    return value.isoformat(timespec="seconds")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    data: dict[str, str] = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data, text[end + 4:]


def read_frontmatter(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    data["_file"] = path.name
    return data


RESERVED = {"HANDOFF-LATEST.md", "HANDOFF-TEMPLATE.md"}


def handoff_files() -> list[Path]:
    return sorted(
        (path for path in HANDOFFS.glob("HANDOFF-*.md")
         if path.name not in RESERVED),
        key=lambda path: path.name,
        reverse=True,
    )


def resolve(query: str | None = None) -> Path | None:
    query = (query or "").strip().lower()
    if not query:
        name = read_frontmatter(LATEST).get("handoff", "")
        candidate = HANDOFFS / name
        if name and candidate.exists():
            return candidate

    matches: list[tuple[str, Path]] = []
    for path in handoff_files():
        frontmatter = read_frontmatter(path)
        haystack = (
            f"{frontmatter.get('handoff_id', '')} {path.stem} "
            f"{frontmatter.get('next', '')}"
        ).lower()
        if not query or query in haystack:
            matches.append((frontmatter.get("handoff_id", ""), path))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def rebuild_index() -> None:
    HANDOFFS.mkdir(parents=True, exist_ok=True)
    rows = [read_frontmatter(path) for path in handoff_files()]
    rows.sort(key=lambda fm: fm.get("handoff_id", ""), reverse=True)
    lines = [
        "# Handoff 索引",
        "",
        (
            "按 `handoff_id` 倒序。由 `scripts/handoff.py` 自动重建；"
            "`HANDOFF-LATEST.md` 指向当前 active 的那一份。"
        ),
        "",
        "| id | file | created | trigger | status | next |",
        "|---|---|---|---|---|---|",
    ]
    for frontmatter in rows:
        name = frontmatter.get("_file", "")
        values = [
            frontmatter.get("handoff_id", ""),
            f"[{name}]({name})",
            frontmatter.get("created", ""),
            frontmatter.get("trigger", ""),
            frontmatter.get("status", ""),
            frontmatter.get("next", ""),
        ]
        lines.append(
            "| " + " | ".join(value.replace("|", "\\|") for value in values)
            + " |")
    INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "handoff")[:40].strip("-")


def one_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def write_latest(path: Path, handoff_id: str, stamp: str, session: str,
                 next_action: str) -> None:
    LATEST.write_text(
        "---\n"
        f"handoff: {path.name}\n"
        f"handoff_id: {handoff_id}\n"
        f"updated: {stamp}\n"
        "status: active\n"
        f"session: {session}\n"
        f"next: {next_action}\n"
        "---\n\n"
        "# 最新 Handoff\n\n"
        f"当前目标文件：`{path.name}`\n\n"
        "恢复时读该文件全文。本文件只是指针，不承载状态；"
        "每次新建 handoff 必须同步更新。\n",
        encoding="utf-8",
    )


def mark_superseded(path: Path, new_name: str) -> None:
    text = path.read_text(encoding="utf-8")
    data, _ = parse_frontmatter(text)
    if data.get("status") != "active":
        return
    text = text.replace(
        "status: active",
        f"status: superseded\nsuperseded_by: {new_name}",
        1,
    )
    path.write_text(text, encoding="utf-8")


def cmd_new(args: argparse.Namespace) -> int:
    HANDOFFS.mkdir(parents=True, exist_ok=True)
    stamp = now()
    handoff_id = stamp.strftime("%Y%m%d-%H%M%S")
    slug = slugify(args.slug)
    path = HANDOFFS / f"HANDOFF-{handoff_id}-{slug}.md"
    if path.exists():
        print(f"refusing to overwrite {path}", file=sys.stderr)
        return 1

    previous = resolve()
    session = args.session or os.environ.get(
        "CLAUDE_CODE_SESSION_ID", "unknown")
    next_action = one_line(args.next_action or "<填写下一步>")
    trigger = one_line(args.trigger or "manual")
    title = one_line(args.title or slug.replace("-", " "))
    reason = one_line(args.reason or f"trigger={trigger}")

    template = TEMPLATE.read_text(encoding="utf-8")
    content = (
        template.replace("{{HANDOFF_ID}}", handoff_id)
        .replace("{{CREATED}}", iso(stamp))
        .replace("{{SESSION}}", session)
        .replace("{{TRIGGER}}", trigger)
        .replace("{{SUPERSEDES}}", previous.name if previous else "null")
        .replace("{{NEXT}}", next_action)
        .replace("{{TITLE}}", title)
        .replace("{{REASON}}", reason)
    )

    if args.dry_run:
        print(f"would write {path}")
        print(content.split("## 目标与当前阶段")[0])
        return 0

    path.write_text(content, encoding="utf-8")
    if previous and previous != path:
        mark_superseded(previous, path.name)
    write_latest(path, handoff_id, iso(stamp), session, next_action)
    rebuild_index()
    print(path)
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    path = resolve(args.query)
    if not path:
        print("no matching handoff", file=sys.stderr)
        return 1
    print(path)
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    for path in handoff_files():
        frontmatter = read_frontmatter(path)
        print(
            f"{frontmatter.get('handoff_id', '?'):<16} "
            f"{frontmatter.get('status', '?'):<10} "
            f"{path.name}\t{frontmatter.get('next', '')}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new",
                         help="create a handoff and update the pointer/index")
    new.add_argument("slug")
    new.add_argument("--trigger", default="manual")
    new.add_argument("--next", dest="next_action", default="")
    new.add_argument("--session", default="")
    new.add_argument("--title", default="")
    new.add_argument("--reason", default="")
    new.add_argument("--dry-run", action="store_true")
    new.set_defaults(func=cmd_new)

    res = sub.add_parser("resolve",
                         help="print the latest or matching handoff path")
    res.add_argument("query", nargs="?")
    res.set_defaults(func=cmd_resolve)

    lst = sub.add_parser("list", help="list handoffs newest first")
    lst.set_defaults(func=cmd_list)

    idx = sub.add_parser("rebuild-index", help="rebuild HANDOFFS.md")
    idx.set_defaults(func=lambda _: (rebuild_index(), 0)[1])

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
