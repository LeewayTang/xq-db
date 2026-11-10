from xqdb.index.fts import rebuild_fts, search
from xqdb.store.db import connect, init_db


def _seed(conn):
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


def test_rebuild_and_search(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn)
    assert rebuild_fts(conn) == 1
    hits = search(conn, "郑伯克段")
    assert hits[0].passage_id == "p:z:1:001" and hits[0].work == "春秋左传"


def test_traditional_query_matches_simplified(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn)
    rebuild_fts(conn)
    assert search(conn, "鄭伯克段")[0].passage_id == "p:z:1:001"


def test_short_query_falls_back_to_like(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn)
    rebuild_fts(conn)
    assert search(conn, "郑伯")[0].passage_id == "p:z:1:001"


def test_dedupes_same_work(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn)
    conn.execute(
        "insert into edition(id,work_id,source_id,char_count,quality_grade) "
        "values('e:z2','w:z','s',10,'A')")
    conn.execute(
        "insert into section(id,edition_id,idx,title,level) "
        "values('s:z2:1','e:z2',1,'隐公元年',1)")
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z2:1:001','s:z2:1',1,'郑伯克段于鄢','郑伯克段于鄢',7)")
    conn.commit()
    rebuild_fts(conn)
    hits = search(conn, "郑伯克段")
    assert len(hits) == 1
