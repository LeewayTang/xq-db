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


def test_search_does_not_starve_other_works(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    conn.execute(
        "insert into source(id,name,url,license,trust) "
        "values('s','s','u','x','secondary')")
    for wid, title in (("w:big", "大书"), ("w:small", "小书")):
        conn.execute("insert into work(id,title) values(?,?)", (wid, title))
        conn.execute(
            "insert into edition(id,work_id,source_id,char_count,quality_grade) "
            "values(?,?,'s',10,'A')", (f"e:{wid}", wid))
        conn.execute(
            "insert into section(id,edition_id,idx,title,level) "
            "values(?,?,1,'章',1)", (f"s:{wid}", f"e:{wid}"))
    for i in range(100):
        conn.execute(
            "insert into passage(id,section_id,idx,text,text_norm,char_count) "
            "values(?,?,?,?,?,7)",
            (f"p:big:{i:03d}", "s:w:big", i, "郑伯克段于鄢", "郑伯克段于鄢"))
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:small:001','s:w:small',1,'郑伯克段于鄢','郑伯克段于鄢',7)")
    conn.commit()
    rebuild_fts(conn)

    hits = search(conn, "郑伯克段", limit=20)
    assert {hit.work for hit in hits} == {"大书", "小书"}


def test_rebuild_indexes_each_section_once(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn)
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:1:002','s:z:1',2,'郑伯克段于鄢二','郑伯克段于鄢二',8)")
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:1:003','s:z:1',3,'郑伯克段于鄢三','郑伯克段于鄢三',8)")
    conn.commit()
    assert rebuild_fts(conn, batch_size=2) == 1
    assert search(conn, "郑伯克段")


def test_incremental_reindex_skips_unchanged_sections(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn)
    assert rebuild_fts(conn, incremental=True) == 1
    assert rebuild_fts(conn, incremental=True) == 0

    conn.execute(
        "insert into section(id,edition_id,idx,title,level) "
        "values('s:z:2','e:z',2,'隐公二年',1)")
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:2:001','s:z:2',1,'公会戎于潜','公会戎于潜',6)")
    conn.commit()
    assert rebuild_fts(conn, incremental=True) == 1
    assert search(conn, "公会戎于潜")


def test_search_returns_matching_passage_inside_section(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    _seed(conn)
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:1:002','s:z:1',2,'郑伯克段于鄢','郑伯克段于鄢',7)")
    conn.execute(
        "update passage set text='无关文字', text_norm='无关文字' "
        "where id='p:z:1:001'")
    conn.commit()
    rebuild_fts(conn)
    hits = search(conn, "郑伯克段")
    assert hits[0].passage_id == "p:z:1:002"


def test_ranking_is_relevance_first_across_works(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    conn.execute(
        "insert into source(id,name,url,license,trust) "
        "values('s','s','u','x','secondary')")
    for wid, title, grade in (("w:a", "甲书", "A"), ("w:b", "乙书", "B")):
        conn.execute("insert into work(id,title) values(?,?)", (wid, title))
        conn.execute(
            "insert into edition(id,work_id,source_id,char_count,quality_grade) "
            "values(?,?,'s',10,?)", (f"e:{wid}", wid, grade))
        conn.execute(
            "insert into section(id,edition_id,idx,title,level) "
            "values(?,?,1,'章',1)", (f"s:{wid}", f"e:{wid}"))
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:a:001','s:w:a',1,?,?,0)",
        ("郑伯克段" + "无关" * 300, "郑伯克段" + "无关" * 300))
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:b:001','s:w:b',1,'郑伯克段郑伯克段郑伯克段',"
        "'郑伯克段郑伯克段郑伯克段',12)")
    conn.commit()
    rebuild_fts(conn)

    hits = search(conn, "郑伯克段")
    assert hits[0].work == "乙书"


def test_dedupe_prefers_higher_grade(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    conn.execute(
        "insert into source(id,name,url,license,trust) "
        "values('s','s','u','x','secondary')")
    conn.execute("insert into work(id,title) values('w:m','某书')")
    conn.execute(
        "insert into edition(id,work_id,source_id,char_count,quality_grade) "
        "values('e:good','w:m','s',10,'A')")
    conn.execute(
        "insert into edition(id,work_id,source_id,char_count,quality_grade) "
        "values('e:bad','w:m','s',10,'B')")
    conn.execute(
        "insert into section(id,edition_id,idx,title,level) "
        "values('s:good','e:good',1,'章',1)")
    conn.execute(
        "insert into section(id,edition_id,idx,title,level) "
        "values('s:bad','e:bad',1,'章',1)")
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:good:001','s:good',1,'郑伯克段于鄢','郑伯克段于鄢',7)")
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:bad:001','s:bad',1,"
        "'郑伯克段于鄢郑伯克段于鄢郑伯克段于鄢',"
        "'郑伯克段于鄢郑伯克段于鄢郑伯克段于鄢',21)")
    conn.commit()
    rebuild_fts(conn)

    hits = search(conn, "郑伯克段")
    assert hits[0].passage_id == "p:good:001"
