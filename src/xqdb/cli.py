import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .config import load_config
from .index.fts import rebuild_fts, search
from .ingest.daizhige import enumerate_corpus, fetch_repo
from .normalize.ids import passage_id, section_id
from .normalize.pipeline import normalize_file
from .normalize.simplify import to_simplified
from .release import build_release
from .review.pipeline import review_batch
from .space.place import resolve_place
from .space.query import passages_in_time, passages_near
from .store.db import connect, init_db

DAIZHIGE_URL = "https://github.com/garychowcmu/daizhigev20"
DEFAULT_SOURCES = {
    "daizhige": ("殆知阁古代文献", DAIZHIGE_URL, "unknown", "tertiary"),
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
    ingest.add_argument("source", choices=["daizhige"])
    ingest.add_argument("--path", default=None, help="本地语料目录")
    ingest.add_argument("--url", default=DAIZHIGE_URL)

    normalize = sub.add_parser("normalize", parents=[common], help="规范化文本")
    normalize.add_argument("--batch", default="default")

    review = sub.add_parser("review", parents=[common], help="审核并分级")
    review.add_argument("--batch", default="default")

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

    return parser


def _cfg(args):
    return load_config(Path(args.root) if args.root else None)


def _connect(args):
    cfg = _cfg(args)
    conn = connect(cfg.db_path)
    init_db(conn)
    return cfg, conn


def _ensure_source(conn, source: str) -> None:
    name, url, license_, trust = DEFAULT_SOURCES[source]
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


def _persist(conn, result, batch: str, cfg) -> None:
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
        "values (?, ?, 'daizhige', ?, ?, ?, 'pending', ?, ?)",
        (result.edition_id, result.work_id, rel_path, result.sha256,
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


def cmd_normalize(args) -> int:
    cfg, conn = _connect(args)
    manifest = cfg.raw_dir / "daizhige" / "manifest.jsonl"
    if not manifest.exists():
        print(f"manifest not found: {manifest}")
        return 1

    entries = [json.loads(line) for line in
               manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    _ensure_source(conn, "daizhige")
    for entry in entries:
        result = normalize_file(
            Path(entry["raw_path"]), entry["rel_path"], "daizhige", cfg.corpus_dir)
        _persist(conn, result, args.batch, cfg)
    conn.commit()
    conn.close()
    print(f"normalized {len(entries)} files")
    return 0


def cmd_review(args) -> int:
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
    print(f"indexed {count} passages")
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
