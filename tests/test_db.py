import sqlite3
from pathlib import Path

import pytest

import xqdb
from xqdb.store.db import SCHEMA_VERSION, connect, init_db


def test_init_creates_core_tables(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    names = {r[0] for r in conn.execute(
        "select name from sqlite_master where type='table'")}
    assert {"source", "work", "edition", "section", "passage",
            "review_finding", "index_meta"} <= names
    assert conn.execute(
        "select value from index_meta where key='schema_version'").fetchone()[0] == SCHEMA_VERSION


def test_init_is_idempotent(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    init_db(conn)
    assert conn.execute("select count(*) from index_meta").fetchone()[0] == 1


def test_foreign_keys_enforced(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "insert into edition(id, work_id, source_id) values('e:x','w:none','s:none')")


def test_packaged_schema_matches_source():
    packaged = Path(xqdb.__file__).with_name("schema.sql")
    source = Path(__file__).resolve().parents[1] / "schemas" / "schema.sql"
    assert packaged.read_bytes() == source.read_bytes()
