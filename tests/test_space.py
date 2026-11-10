from xqdb.cli import main
from xqdb.space.place import (
    add_location,
    add_name,
    haversine_km,
    resolve_place,
    upsert_place,
)
from xqdb.space.query import passages_in_time, passages_near
from xqdb.store.db import connect, init_db


def _place(conn):
    upsert_place(conn, "pl:xinzheng", "新郑", "邑")
    add_name(conn, "pl:xinzheng", "郑", "ancient", period="春秋", is_preferred=True)
    add_name(conn, "pl:xinzheng", "新郑市", "modern", is_preferred=True)
    add_location(
        conn, "pl:xinzheng", 34.39, 113.74, precision_m=5000,
        modern_province="河南", modern_city="郑州", modern_county="新郑",
        is_primary=True)
    upsert_place(conn, "pl:mingtiao", "鸣条", "战场")
    add_name(conn, "pl:mingtiao", "鸣条", "ancient", is_preferred=True)
    add_location(conn, "pl:mingtiao", 35.03, 111.22,
                 hypothesis="安邑说", confidence=0.4)
    add_location(conn, "pl:mingtiao", 35.14, 111.22,
                 hypothesis="夏县说", confidence=0.3)
    conn.commit()


def _seed_passage(conn, year_start, year_end, place=None):
    conn.execute(
        "insert or ignore into source(id,name,url,license,trust) "
        "values('s','s','u','x','secondary')")
    conn.execute("insert or ignore into work(id,title) values('w:t','测试')")
    conn.execute(
        "insert or ignore into edition"
        "(id,work_id,source_id,char_count,quality_grade) "
        "values('e:t','w:t','s',10,'A')")
    conn.execute(
        "insert or ignore into section(id,edition_id,idx,title,level) "
        "values('st:1','e:t',1,'章',1)")
    conn.execute(
        "insert or ignore into passage"
        "(id,section_id,idx,text,text_norm,char_count) "
        "values('p:t:1:001','st:1',1,'郑伯克段于鄢','郑伯克段于鄢',7)")
    conn.execute(
        "insert into passage_time"
        "(passage_id,year_start,year_end,confidence,basis) "
        "values('p:t:1:001',?,?,'high','test')", (year_start, year_end))
    if place:
        conn.execute(
            "insert into passage_place(passage_id,place_id,role,confidence) "
            "values('p:t:1:001',?,'mention',0.9)", (place,))
    conn.commit()


def test_resolve_by_ancient_and_modern_name(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _place(conn)
    assert resolve_place(conn, "郑")[0].place_id == "pl:xinzheng"
    assert resolve_place(conn, "新郑市")[0].place_id == "pl:xinzheng"


def test_multiple_location_hypotheses_preserved(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _place(conn)
    matches = [m for m in resolve_place(conn, "鸣条") if m.lat is not None]
    assert len(matches) == 2


def test_haversine():
    distance = haversine_km(39.90, 116.40, 31.23, 121.47)
    assert 1000 < distance < 1200


def test_time_overlap(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed_passage(conn, -770, -750)
    assert passages_in_time(conn, -760, -755)[0].passage_id == "p:t:1:001"
    assert passages_in_time(conn, -700, -690) == []


def test_near_radius(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _place(conn)
    _seed_passage(conn, -770, -750, place="pl:xinzheng")
    assert passages_near(conn, 34.40, 113.75, 50)[0].passage_id == "p:t:1:001"
    assert passages_near(conn, 31.23, 121.47, 50) == []


def test_cli_place(tmp_path, capsys):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("", encoding="utf-8")
    (tmp_path / "data").mkdir()
    conn = connect(tmp_path / "data" / "xq_index.db")
    init_db(conn)
    _place(conn)
    conn.close()
    assert main(["--root", str(tmp_path), "place", "新郑"]) == 0
    out = capsys.readouterr().out
    assert "新郑" in out and "113.74" in out
