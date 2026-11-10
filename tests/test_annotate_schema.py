import sqlite3

import pytest

from xqdb.store.db import connect, init_db


def test_annotation_state_table_exists(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    columns = {row[1] for row in conn.execute(
        "pragma table_info(annotation_state)")}
    assert {"chunk_id", "section_id", "status", "attempts",
            "error", "model", "updated_at"} <= columns


def test_annotation_state_status_is_constrained(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    conn.execute("insert into source(id,name,url,license,trust) "
                 "values('s','s','u','x','secondary')")
    conn.execute("insert into work(id,title) values('w','书')")
    conn.execute("insert into edition(id,work_id,source_id,char_count,quality_grade) "
                 "values('e','w','s',10,'A')")
    conn.execute("insert into section(id,edition_id,idx,title,level) "
                 "values('s1','e',1,'章',1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "insert into annotation_state(chunk_id,section_id,status,updated_at) "
            "values('c1','s1','bogus','now')")
