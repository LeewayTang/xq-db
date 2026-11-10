from xqdb.review.pipeline import review_batch
from xqdb.store.db import connect, init_db


def _seed(conn, n):
    conn.execute(
        "insert into source(id,name,url,license,trust) "
        "values('s','s','u','x','tertiary')")
    for i in range(n):
        conn.execute("insert into work(id,title) values(?,?)", (f"w:{i}", f"书{i}"))
        conn.execute(
            "insert into edition(id,work_id,source_id,path,char_count,batch_id) "
            "values(?,?, 's', ?, ?, 'b1')",
            (f"e:{i}", f"w:{i}", f"{i}.md", 100))
    conn.commit()


def test_gate_blocks_high_q_rate(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn, 10)
    (tmp_path / "corpus").mkdir()
    for i in range(10):
        (tmp_path / "corpus" / f"{i}.md").write_text("正常" * 50, encoding="utf-8")
    (tmp_path / "corpus" / "0.md").write_text("�" * 100, encoding="utf-8")
    rep = review_batch(conn, "b1", tmp_path / "corpus")
    assert rep.q_rate >= 0.1 and rep.blocked is True


def test_gate_allows_low_q_rate(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn, 20)
    (tmp_path / "corpus").mkdir()
    for i in range(20):
        (tmp_path / "corpus" / f"{i}.md").write_text("正常" * 100, encoding="utf-8")
    (tmp_path / "corpus" / "0.md").write_text("�" * 100, encoding="utf-8")
    rep = review_batch(conn, "b1", tmp_path / "corpus")
    assert rep.q_rate == 0.05 and rep.blocked is False


def test_empty_batch_is_not_blocked(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    (tmp_path / "corpus").mkdir()
    rep = review_batch(conn, "none", tmp_path / "corpus")
    assert rep.total == 0 and rep.blocked is False


def test_missing_file_does_not_crash(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn, 1)
    (tmp_path / "corpus").mkdir()
    rep = review_batch(conn, "b1", tmp_path / "corpus")
    assert rep.total == 1
    assert rep.results[0].quality_grade == "C"


def test_duplicate_detection_wired(tmp_path):
    from xqdb.normalize.simhash import simhash64

    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn, 2)
    (tmp_path / "corpus").mkdir()
    text = "左传隐公元年郑伯克段于鄢" * 30
    for i in range(2):
        (tmp_path / "corpus" / f"{i}.md").write_text(text, encoding="utf-8")
    conn.execute("update edition set simhash = ?", (simhash64(text),))
    conn.commit()

    rep = review_batch(conn, "b1", tmp_path / "corpus")
    kinds = {finding.kind for result in rep.results
             for finding in result.findings}
    assert "high_duplication" in kinds
