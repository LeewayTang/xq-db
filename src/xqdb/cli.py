import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .annotate.batch import annotate_batch
from .annotate.export import export_knowledge
from .config import load_config
from .harness.budget import Budget
from .harness.client import AnthropicClient
from .harness.config import load_agent_config
from .harness.roles import load_roles
from .harness.runlog import month_to_date_cost
from .harness.runner import Runner
from .index.fts import rebuild_fts, search
from .ingest.daizhige import enumerate_corpus, fetch_repo
from .ingest.wikisource import CORE_TITLES, fetch_documents, write_pages
from .normalize.ids import edition_id, passage_id, section_id, work_id
from .normalize.pipeline import normalize_file
from .normalize.simplify import to_simplified
from .release import build_release
from .review.llm import review_llm_batch
from .review.pipeline import review_batch
from .space.place import resolve_place
from .space.query import passages_in_time, passages_near
from .store.db import connect, init_db
from .tools.context import tool_context
from .tools.registry import TOOL_SPECS

DAIZHIGE_URL = "https://github.com/garychowcmu/daizhigev20"
DEFAULT_SOURCES = {
    "daizhige": ("殆知阁古代文献", DAIZHIGE_URL, "unknown", "tertiary"),
    "wikisource": ("中文维基文库", "https://zh.wikisource.org",
                   "CC-BY-SA-4.0", "secondary"),
}


def _common() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", default=argparse.SUPPRESS)
    return parser


def build_parser() -> argparse.ArgumentParser:
    common = _common()
    parser = argparse.ArgumentParser(prog="xqdb")
    parser.add_argument("--root", default=None, help="仓库根目录，默认当前目录")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="打印版本")
    sub.add_parser("init", parents=[common], help="初始化数据目录与数据库")

    ingest = sub.add_parser("ingest", parents=[common], help="采集语料")
    ingest.add_argument("source", choices=["daizhige", "wikisource"])
    ingest.add_argument("--path", default=None, help="本地语料目录")
    ingest.add_argument("--url", default=DAIZHIGE_URL)

    normalize = sub.add_parser("normalize", parents=[common], help="规范化文本")
    normalize.add_argument("--batch", default="default")
    normalize.add_argument("--force", action="store_true",
                           help="覆盖已存在的版本")
    normalize.add_argument("--force-annotated", action="store_true",
                           help="允许覆盖已有标注/审核记录的版本")
    normalize.add_argument("--source", default=None,
                           help="只处理某个语料源")

    review = sub.add_parser("review", parents=[common], help="审核并分级")
    review.add_argument("--batch", default="default")
    review.add_argument("--llm", action="store_true")
    review.add_argument("--limit", type=int, default=20)
    review.add_argument("--dry-run", action="store_true")

    sub.add_parser("index", parents=[common], help="重建全文索引")

    query = sub.add_parser("search", parents=[common], help="全文检索")
    query.add_argument("query")
    query.add_argument("--limit", type=int, default=20)
    query.add_argument("--grades", default="A,B")

    sub.add_parser("stats", parents=[common], help="语料统计")

    release = sub.add_parser("release", parents=[common], help="打包数据 Release")
    release.add_argument("--tag", required=True)

    place = sub.add_parser("place", parents=[common], help="解析地名")
    place.add_argument("name")

    near = sub.add_parser("near", parents=[common], help="按地理半径检索")
    near.add_argument("lat", type=float)
    near.add_argument("lon", type=float)
    near.add_argument("--radius", type=float, default=50.0)

    when = sub.add_parser("when", parents=[common], help="按时间范围检索")
    when.add_argument("start", type=int)
    when.add_argument("end", type=int)

    sub.add_parser("tools", parents=[common], help="列出可用工具")

    agent = sub.add_parser("agent", parents=[common], help="Agent 角色与运行")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    agent_sub.add_parser("roles", help="列出角色")
    run = agent_sub.add_parser("run", help="运行角色")
    run.add_argument("--role", required=True)
    run.add_argument("--task", required=True)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--max-tokens", type=int)
    run.add_argument("--max-tool-calls", type=int)
    run.add_argument("--max-cost", type=float)

    annotate = sub.add_parser("annotate", parents=[common], help="语料标注")
    annotate_sub = annotate.add_subparsers(
        dest="annotate_command", required=True)
    annotate_run = annotate_sub.add_parser("run", help="批量标注")
    annotate_run.add_argument("--role", required=True)
    annotate_run.add_argument("--limit", type=int, default=20)
    annotate_run.add_argument("--chunk-size", type=int, default=4000)
    annotate_run.add_argument("--dry-run", action="store_true")
    annotate_run.add_argument("--force", action="store_true")
    annotate_export = annotate_sub.add_parser("export", help="导出知识层")
    annotate_export.add_argument("--out", default=None)

    return parser


def _cfg(args):
    return load_config(Path(args.root) if args.root else None)


def _connect(args):
    cfg = _cfg(args)
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg.db_path)
    init_db(conn)
    return cfg, conn


def _ensure_source(conn, source: str) -> None:
    name, url, license_, trust = DEFAULT_SOURCES.get(
        source, (source, "", "unknown", "unknown"))
    conn.execute(
        "insert or ignore into source(id, name, url, license, trust) "
        "values (?, ?, ?, ?, ?)",
        (source, name, url, license_, trust),
    )


def cmd_init(args) -> int:
    cfg = _cfg(args)
    for directory in (cfg.data_dir, cfg.raw_dir, cfg.corpus_dir, cfg.knowledge_dir):
        directory.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg.db_path)
    init_db(conn)
    conn.close()
    print(f"initialized {cfg.db_path}")
    return 0


def cmd_ingest(args) -> int:
    cfg = _cfg(args)
    if args.source == "wikisource":
        import httpx

        with httpx.Client(timeout=60, follow_redirects=True) as client:
            pages = fetch_documents(CORE_TITLES, client)
        files = write_pages(pages, cfg.raw_dir)
        print(f"ingested {len(files)} pages from wikisource")
        return 0

    if args.path:
        repo = Path(args.path).resolve()
    else:
        repo = fetch_repo(cfg.raw_dir / args.source / "repo", args.url)

    files = enumerate_corpus(repo)
    manifest = cfg.raw_dir / args.source / "manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", encoding="utf-8") as handle:
        for item in files:
            handle.write(json.dumps({
                "rel_path": item.rel_path,
                "raw_path": str(item.path),
                "sha256": item.sha256,
                "size": item.size,
            }, ensure_ascii=False) + "\n")
    print(f"ingested {len(files)} files from {repo}")
    return 0


def _persist(conn, result, batch: str, cfg, source: str) -> None:
    conn.execute(
        "insert or ignore into work(id, title) values (?, ?)",
        (result.work_id, result.title),
    )
    conn.execute("delete from edition where id = ?", (result.edition_id,))
    rel_path = result.path.relative_to(cfg.corpus_dir).as_posix()
    conn.execute(
        "insert into edition"
        "(id, work_id, source_id, path, sha256, char_count, review_status,"
        " batch_id, simhash) "
        "values (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
        (result.edition_id, result.work_id, source, rel_path, result.sha256,
         result.char_count, batch, result.simhash),
    )
    for section_index, section in enumerate(result.sections, start=1):
        sid = section_id(result.edition_id, (section_index,))
        conn.execute(
            "insert into section(id, edition_id, idx, title, level) "
            "values (?, ?, ?, ?, ?)",
            (sid, result.edition_id, section_index, section.title, section.level),
        )
        passage_index = 0
        for line in section.lines:
            if not line.strip():
                continue
            passage_index += 1
            conn.execute(
                "insert into passage"
                "(id, section_id, idx, text, text_norm, char_count) "
                "values (?, ?, ?, ?, ?, ?)",
                (passage_id(sid, passage_index), sid, passage_index,
                 line, to_simplified(line), len(line)),
            )


def _has_dependents(conn, edition_id: str) -> bool:
    count = conn.execute(
        """
        select
          (select count(*) from review_finding where edition_id = ?)
        + (select count(*) from mention m
             join passage p on p.id = m.passage_id
             join section s on s.id = p.section_id
             where s.edition_id = ?)
        + (select count(*) from highlight h
             join passage p on p.id = h.passage_id
             join section s on s.id = p.section_id
             where s.edition_id = ?)
        + (select count(*) from seed_passage sp
             join passage p on p.id = sp.passage_id
             join section s on s.id = p.section_id
             where s.edition_id = ?)
        + (select count(*) from note
             where target_type = 'edition' and target_id = ?)
        """,
        (edition_id, edition_id, edition_id, edition_id, edition_id),
    ).fetchone()[0]
    return count > 0


def cmd_normalize(args) -> int:
    cfg, conn = _connect(args)
    manifests = sorted(cfg.raw_dir.glob("*/manifest.jsonl"))
    if args.source:
        manifests = [
            manifest for manifest in manifests
            if manifest.parent.name == args.source]
    if not manifests:
        print(f"no manifest found under {cfg.raw_dir}")
        return 1

    normalized = skipped = errors = 0

    for manifest in manifests:
        source = manifest.parent.name
        entries = [json.loads(line) for line in
                   manifest.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        _ensure_source(conn, source)

        for entry in entries:
            rel_path = entry["rel_path"]
            base_work = work_id(Path(rel_path).stem)
            edition = edition_id(base_work, source)
            suffix = None

            row = conn.execute(
                "select sha256 from edition where id = ?",
                (edition,)).fetchone()
            if row is not None:
                same_content = row["sha256"] == entry.get("sha256")
                if same_content and not args.force:
                    skipped += 1
                    continue
                if not same_content:
                    suffix = hashlib.sha1(
                        rel_path.encode("utf-8")).hexdigest()[:6]
                    edition = edition_id(f"{base_work}-{suffix}", source)
                    variant = conn.execute(
                        "select 1 from edition where id = ?",
                        (edition,)).fetchone()
                    if variant is not None and not args.force:
                        skipped += 1
                        continue
                if (args.force and not args.force_annotated
                        and _has_dependents(conn, edition)):
                    errors += 1
                    print(
                        f"blocked {rel_path}: edition has annotations; "
                        "use --force-annotated to override")
                    continue

            try:
                result = normalize_file(
                    Path(entry["raw_path"]), rel_path, source,
                    cfg.corpus_dir, work_suffix=suffix)
            except Exception as exc:  # noqa: BLE001 - keep the batch alive
                errors += 1
                print(f"failed {rel_path}: {exc}")
                continue
            _persist(conn, result, args.batch, cfg, source)
            normalized += 1

    conn.commit()
    conn.close()
    print(f"normalized {normalized}, skipped {skipped}, failed {errors}")
    return 1 if errors else 0


def cmd_review(args) -> int:
    if args.llm:
        if args.dry_run:
            cfg, conn = _connect(args)
            count = conn.execute("select count(*) from edition").fetchone()[0]
            conn.close()
            print(f"would review {count} editions")
            return 0

        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set; export it or use --dry-run")
            return 1

        cfg = _cfg(args)
        agent_cfg = load_agent_config(cfg.root)
        roles = load_roles(
            agent_cfg.agents_dir, schemas_dir=agent_cfg.schemas_dir)
        role = roles.get("reviewer")
        if role is None:
            print("reviewer role not found")
            return 1
        if _monthly_budget_exceeded(agent_cfg, role):
            return 1
        budget = Budget(
            role.max_tokens, role.max_tool_calls, role.max_cost_usd)
        with tool_context(cfg.root) as ctx:
            report = review_llm_batch(
                ctx.conn, role,
                lambda: AnthropicClient(
                    agent_cfg.model, prices=agent_cfg.prices),
                budget, agent_cfg.runs_dir, ctx, limit=args.limit)
        print(f"llm review: checked={report.checked} "
              f"updated={report.updated} "
              f"findings={report.findings_written} "
              f"stopped={report.stopped_reason}")
        return 0

    cfg, conn = _connect(args)
    report = review_batch(conn, args.batch, cfg.corpus_dir)
    conn.close()
    print(
        f"reviewed {report.total}: Q={report.q_count} "
        f"rate={report.q_rate:.2%} blocked={report.blocked}")
    return 1 if report.blocked else 0


def cmd_index(args) -> int:
    _, conn = _connect(args)
    count = rebuild_fts(conn)
    conn.close()
    print(f"indexed {count} sections")
    return 0


def cmd_search(args) -> int:
    _, conn = _connect(args)
    grades = tuple(g.strip() for g in args.grades.split(",") if g.strip())
    hits = search(conn, args.query, limit=args.limit, grades=grades)
    conn.close()
    if not hits:
        print("no results")
        return 0
    for hit in hits:
        print(f"[{hit.passage_id}] {hit.work} · {hit.section}")
        print(f"  {hit.text}")
    return 0


def cmd_stats(args) -> int:
    _, conn = _connect(args)
    for label, sql in (
        ("works", "select count(*) from work"),
        ("editions", "select count(*) from edition"),
        ("sections", "select count(*) from section"),
        ("passages", "select count(*) from passage"),
    ):
        print(f"{label}: {conn.execute(sql).fetchone()[0]}")
    for row in conn.execute(
        "select quality_grade, count(*) from edition "
        "group by quality_grade order by quality_grade"):
        print(f"grade {row[0]}: {row[1]}")
    conn.close()
    return 0


def cmd_place(args) -> int:
    _, conn = _connect(args)
    matches = resolve_place(conn, args.name)
    conn.close()
    if not matches:
        print("no results")
        return 0
    for match in matches:
        coords = (f"{match.lat:.4f},{match.lon:.4f}"
                  if match.lat is not None else "?")
        modern = f" ({match.modern_name})" if match.modern_name else ""
        print(f"[{match.place_id}] {match.canonical_name} · "
              f"{match.matched_name}/{match.name_type} {coords}{modern}")
    return 0


def _print_hits(hits) -> None:
    if not hits:
        print("no results")
        return
    for hit in hits:
        print(f"[{hit.passage_id}] {hit.work} · {hit.section}")
        print(f"  {hit.text}")


def cmd_near(args) -> int:
    _, conn = _connect(args)
    hits = passages_near(conn, args.lat, args.lon, args.radius)
    conn.close()
    _print_hits(hits)
    return 0


def cmd_when(args) -> int:
    _, conn = _connect(args)
    hits = passages_in_time(conn, args.start, args.end)
    conn.close()
    _print_hits(hits)
    return 0


def cmd_tools(args) -> int:
    for name, spec in TOOL_SPECS.items():
        if not spec.admin:
            print(f"{name}: {spec.description}")
    return 0


def _monthly_budget_exceeded(agent_cfg, role) -> bool:
    spent = month_to_date_cost(agent_cfg.runs_dir)
    if spent + role.max_cost_usd > agent_cfg.monthly_budget_usd:
        print(f"monthly budget exceeded: spent ${spent:.2f}, "
              f"cap ${agent_cfg.monthly_budget_usd:.2f}")
        return True
    return False


def cmd_agent(args) -> int:
    cfg = load_agent_config(Path(args.root) if args.root else None)
    roles = load_roles(cfg.agents_dir, schemas_dir=cfg.schemas_dir)

    if args.agent_command == "roles":
        for role in roles.values():
            print(f"{role.name}: tools={len(role.tools)} "
                  f"budget=${role.max_cost_usd:.2f} tokens={role.max_tokens}")
        return 0

    role = roles.get(args.role)
    if role is None:
        print(f"unknown role: {args.role}")
        return 1

    if args.dry_run:
        print(json.dumps({
            "role": role.name,
            "tools": list(role.tools),
            "budget": {
                "max_tokens": role.max_tokens,
                "max_tool_calls": role.max_tool_calls,
                "max_cost_usd": role.max_cost_usd,
            },
            "prompt": role.prompt,
        }, ensure_ascii=False, indent=2))
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; export it or use --dry-run")
        return 1

    spent = month_to_date_cost(cfg.runs_dir)
    if spent + role.max_cost_usd > cfg.monthly_budget_usd:
        print(f"monthly budget exceeded: spent ${spent:.2f}, "
              f"cap ${cfg.monthly_budget_usd:.2f}")
        return 1

    budget = Budget(
        max_tokens=args.max_tokens or role.max_tokens,
        max_tool_calls=args.max_tool_calls or role.max_tool_calls,
        max_cost_usd=(args.max_cost if args.max_cost is not None
                      else role.max_cost_usd),
    )
    root = Path(args.root) if args.root else None
    with tool_context(root) as ctx:
        result = Runner(
            role, TOOL_SPECS, AnthropicClient(cfg.model, prices=cfg.prices), budget,
            cfg.runs_dir, ctx=ctx).run(args.task)
    print(result.output)
    print(f"status={result.status} citations={result.citations} "
          f"log={result.log_path}")
    return 0 if result.status == "ok" else 1


def cmd_annotate(args) -> int:
    cfg = _cfg(args)

    if args.annotate_command == "export":
        cfg, conn = _connect(args)
        out = Path(args.out) if args.out else cfg.knowledge_dir
        counts = export_knowledge(conn, out)
        conn.close()
        print(" ".join(f"{key}={value}" for key, value in counts.items()))
        return 0

    agent_cfg = load_agent_config(cfg.root)
    roles = load_roles(
        agent_cfg.agents_dir, schemas_dir=agent_cfg.schemas_dir)
    role = roles.get(args.role)
    if role is None:
        print(f"unknown role: {args.role}")
        return 1

    budget = Budget(role.max_tokens, role.max_tool_calls, role.max_cost_usd)
    if args.dry_run:
        with tool_context(cfg.root) as ctx:
            result = annotate_batch(
                ctx.conn, role, None, budget, agent_cfg.runs_dir, ctx,
                limit=args.limit, max_chars=args.chunk_size,
                dry_run=True, force=args.force)
        print(f"annotate dry-run: chunks={result.processed}")
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; export it or use --dry-run")
        return 1

    if _monthly_budget_exceeded(agent_cfg, role):
        return 1

    with tool_context(cfg.root) as ctx:
        result = annotate_batch(
            ctx.conn, role,
            AnthropicClient(agent_cfg.model, prices=agent_cfg.prices),
            budget, agent_cfg.runs_dir, ctx,
            limit=args.limit, max_chars=args.chunk_size, force=args.force)
    print(f"annotate: processed={result.processed} ok={result.ok} "
          f"failed={result.failed} rejected={result.rejected} "
          f"stopped={result.stopped_reason}")
    return 0 if result.stopped_reason is None else 1


def cmd_release(args) -> int:
    cfg = _cfg(args)
    out = build_release(cfg.root, args.tag)
    print(f"release written to {out}")
    return 0


COMMANDS = {
    "init": cmd_init,
    "ingest": cmd_ingest,
    "normalize": cmd_normalize,
    "review": cmd_review,
    "index": cmd_index,
    "search": cmd_search,
    "stats": cmd_stats,
    "release": cmd_release,
    "place": cmd_place,
    "near": cmd_near,
    "when": cmd_when,
    "tools": cmd_tools,
    "agent": cmd_agent,
    "annotate": cmd_annotate,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "version":
        print(f"xqdb {__version__}")
        return 0
    handler = COMMANDS.get(args.command)
    if handler is None:
        return 1
    return handler(args)
