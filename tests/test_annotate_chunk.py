from xqdb.annotate.chunk import iter_chunks


def _seed(conn):
    conn.execute("insert or ignore into source(id,name,url,license,trust) "
                 "values('s','s','u','x','secondary')")
    conn.execute("insert or ignore into work(id,title) values('w','书')")
    conn.execute("insert or ignore into edition"
                 "(id,work_id,source_id,char_count,quality_grade) "
                 "values('e','w','s',100,'A')")
    for i in (1, 2):
        conn.execute("insert or ignore into section(id,edition_id,idx,title,level) "
                     "values(?,?,?,?,1)", (f"s{i}", "e", i, f"章{i}"))
    rows = [
        ("p:1:001", "s1", 1, "甲" * 10),
        ("p:1:002", "s1", 2, "乙" * 10),
        ("p:2:001", "s2", 1, "丙" * 10),
    ]
    for pid, sid, idx, text in rows:
        conn.execute("insert or ignore into passage"
                     "(id,section_id,idx,text,text_norm,char_count) "
                     "values(?,?,?,?,?,?)", (pid, sid, idx, text, text, len(text)))
    conn.commit()


def test_chunks_are_deterministic_and_bounded(ctx):
    _seed(ctx.conn)
    first = list(iter_chunks(ctx.conn, max_chars=15))
    second = list(iter_chunks(ctx.conn, max_chars=15))
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert all(c.char_count <= 15 or len(c.passage_ids) == 1 for c in first)
    assert first[0].chunk_id == "s1#001"


def test_only_unannotated_skips_ok_sections(ctx):
    _seed(ctx.conn)
    ctx.conn.execute("insert into annotation_state"
                     "(chunk_id,section_id,status,updated_at) "
                     "values('s1#001','s1','ok','now')")
    ctx.conn.commit()
    assert all(c.section_id != "s1" for c in iter_chunks(
        ctx.conn, only_unannotated=True))


def test_empty_sections_produce_no_chunks(ctx):
    ctx.conn.execute("delete from passage")
    ctx.conn.commit()
    assert list(iter_chunks(ctx.conn)) == []
