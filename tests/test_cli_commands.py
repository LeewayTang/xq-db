from pathlib import Path

from xqdb.catalog.build import build_index_jsonl
from xqdb.cli import main
from xqdb.store.db import connect

LONG = "".join(chr(0x4E00 + i) for i in range(200)) + "郑伯克段于鄢。"


def _project(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("", encoding="utf-8")
    return tmp_path


def _raw_tree(tmp_path: Path) -> Path:
    repo = tmp_path / "rawsrc"
    path = repo / "儒藏" / "春秋" / "春秋左传.txt"
    path.parent.mkdir(parents=True)
    path.write_text("◇隐公元年\n" + LONG + "\n", encoding="utf-8")
    return repo


def _pipeline(tmp_path: Path) -> Path:
    _project(tmp_path)
    repo = _raw_tree(tmp_path)
    assert main(["--root", str(tmp_path), "init"]) == 0
    assert main(["--root", str(tmp_path), "ingest", "daizhige",
                 "--path", str(repo)]) == 0
    assert main(["--root", str(tmp_path), "normalize"]) == 0
    assert main(["--root", str(tmp_path), "review"]) == 0
    assert main(["--root", str(tmp_path), "index"]) == 0
    return tmp_path / "data" / "xq_index.db"


def test_init_creates_db(tmp_path):
    _project(tmp_path)
    assert main(["--root", str(tmp_path), "init"]) == 0
    assert (tmp_path / "data" / "xq_index.db").exists()


def test_search_returns_citation(tmp_path, capsys):
    _project(tmp_path)
    (tmp_path / "data").mkdir()
    from xqdb.index.fts import rebuild_fts
    from xqdb.store.db import init_db

    conn = connect(tmp_path / "data" / "xq_index.db")
    init_db(conn)
    conn.execute(
        "insert into source(id,name,url,license,trust) "
        "values('s','s','u','x','secondary')")
    conn.execute("insert into work(id,title) values('w:z','春秋左传')")
    conn.execute(
        "insert into edition(id,work_id,source_id,char_count,quality_grade) "
        "values('e:z','w:z','s',10,'A')")
    conn.execute(
        "insert into section(id,edition_id,idx,title,level) "
        "values('s:z:1','e:z',1,'隐公元年',1)")
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:1:001','s:z:1',1,'郑伯克段于鄢','郑伯克段于鄢',7)")
    conn.commit()
    rebuild_fts(conn)
    conn.close()
    assert main(["search", "郑伯克段", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "[p:z:1:001]" in out and "春秋左传" in out


def test_pipeline_end_to_end(tmp_path, capsys):
    db = _pipeline(tmp_path)
    conn = connect(db)
    assert conn.execute("select count(*) from edition").fetchone()[0] == 1
    assert conn.execute("select count(*) from passage").fetchone()[0] >= 1
    assert conn.execute(
        "select quality_grade from edition").fetchone()[0] == "A"
    conn.close()

    capsys.readouterr()
    assert main(["--root", str(tmp_path), "search", "郑伯克段"]) == 0
    out = capsys.readouterr().out
    assert "春秋左传" in out and "隐公元年" in out


def test_stats_reports_counts(tmp_path, capsys):
    _pipeline(tmp_path)
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "stats"]) == 0
    out = capsys.readouterr().out
    assert "works" in out and "passages" in out


def test_catalog_export(tmp_path):
    db = _pipeline(tmp_path)
    conn = connect(db)
    out = tmp_path / "works.jsonl"
    assert build_index_jsonl(conn, out) == 1
    text = out.read_text(encoding="utf-8")
    assert "春秋左传" in text


def test_release_command(tmp_path):
    _pipeline(tmp_path)
    assert main(["--root", str(tmp_path), "release", "--tag", "data-v0.1.0"]) == 0
    assert (tmp_path / "dist" / "data-v0.1.0" / "MANIFEST.json").exists()


def test_normalize_handles_wikisource_manifest(tmp_path):
    import hashlib
    import json

    _project(tmp_path)
    raw_dir = tmp_path / "data" / "raw" / "wikisource"
    raw_dir.mkdir(parents=True)
    text = "子曰：学而时习之。\n"
    (raw_dir / "论语.txt").write_text(text, encoding="utf-8")
    data = text.encode("utf-8")
    (raw_dir / "manifest.jsonl").write_text(json.dumps({
        "rel_path": "论语.txt",
        "raw_path": str(raw_dir / "论语.txt"),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    assert main(["--root", str(tmp_path), "init"]) == 0
    assert main(["--root", str(tmp_path), "normalize"]) == 0

    conn = connect(tmp_path / "data" / "xq_index.db")
    assert conn.execute(
        "select source_id from edition").fetchone()[0] == "wikisource"


def test_normalize_skips_existing_without_force(tmp_path):
    db = _pipeline(tmp_path)
    conn = connect(db)
    conn.execute("update edition set char_count = 999")
    conn.commit()
    conn.close()

    assert main(["--root", str(tmp_path), "normalize"]) == 0
    conn = connect(db)
    assert conn.execute("select char_count from edition").fetchone()[0] == 999
    conn.close()

    assert main(["--root", str(tmp_path), "normalize", "--force"]) == 0
    conn = connect(db)
    assert conn.execute("select char_count from edition").fetchone()[0] != 999


def test_normalize_continues_after_missing_file(tmp_path):
    _project(tmp_path)
    repo = _raw_tree(tmp_path)
    assert main(["--root", str(tmp_path), "init"]) == 0
    assert main(["--root", str(tmp_path), "ingest", "daizhige",
                 "--path", str(repo)]) == 0

    manifest = tmp_path / "data" / "raw" / "daizhige" / "manifest.jsonl"
    line = manifest.read_text(encoding="utf-8").strip()
    missing = line.replace("春秋左传.txt", "缺失.txt")
    manifest.write_text(line + "\n" + missing + "\n", encoding="utf-8")

    assert main(["--root", str(tmp_path), "normalize"]) == 1
    conn = connect(tmp_path / "data" / "xq_index.db")
    assert conn.execute("select count(*) from edition").fetchone()[0] == 1


def test_catalog_prefers_best_grade(tmp_path):
    import json

    db = _pipeline(tmp_path)
    conn = connect(db)
    work_id = conn.execute("select id from work").fetchone()[0]
    conn.execute(
        "insert into edition(id,work_id,source_id,quality_grade) "
        "values('e:q',?,'daizhige','Q')", (work_id,))
    conn.commit()

    out = tmp_path / "works.jsonl"
    build_index_jsonl(conn, out)
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["best_grade"] == "A"


def test_force_refuses_when_review_findings_exist(tmp_path):
    db = _pipeline(tmp_path)
    conn = connect(db)
    conn.execute("delete from review_finding")
    edition_id = conn.execute("select id from edition").fetchone()[0]
    conn.execute(
        "insert into review_finding(edition_id,kind,severity,decided_at) "
        "values(?, 'low_information', 'warn', 'now')", (edition_id,))
    conn.commit()
    conn.close()

    assert main(["--root", str(tmp_path), "normalize", "--force"]) == 1
    conn = connect(db)
    assert conn.execute(
        "select count(*) from edition where id = ?", (edition_id,)
    ).fetchone()[0] == 1
    assert conn.execute("select count(*) from review_finding").fetchone()[0] == 1


def test_same_title_different_content_get_distinct_works(tmp_path):
    _project(tmp_path)
    repo = tmp_path / "rawsrc"
    first = repo / "子藏" / "甲" / "春秋.txt"
    second = repo / "子藏" / "乙" / "春秋.txt"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("◇甲\n" + LONG + "\n", encoding="utf-8")
    second.write_text(
        "◇乙\n" + "".join(chr(0x6000 + i) for i in range(200)) + "。\n",
        encoding="utf-8")

    assert main(["--root", str(tmp_path), "init"]) == 0
    assert main(["--root", str(tmp_path), "ingest", "daizhige",
                 "--path", str(repo)]) == 0
    assert main(["--root", str(tmp_path), "normalize"]) == 0

    conn = connect(tmp_path / "data" / "xq_index.db")
    assert conn.execute("select count(*) from work").fetchone()[0] == 2
    assert conn.execute("select count(*) from edition").fetchone()[0] == 2
