import json
import sqlite3
from pathlib import Path

import pytest

from xqdb.annotate.schema import (
    AnnotationInvalid,
    parse_annotation,
    validate_annotation,
)
from xqdb.store.db import connect, init_db

SCHEMA = Path("schemas/agents/annotator.schema.json")
FIXTURE = Path("tests/fixtures/annotations/zuozhuan.json")


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


def test_fixture_passes_schema():
    validate_annotation(json.loads(FIXTURE.read_text("utf-8")), SCHEMA)


def test_missing_passage_id_rejected():
    with pytest.raises(AnnotationInvalid):
        validate_annotation(
            {"entities": [{"type": "person", "name": "郑庄公"}]}, SCHEMA)


def test_parse_strips_markdown_fence():
    payload = parse_annotation("```json\n{\"entities\": []}\n```")
    assert payload == {"entities": []}


def test_parse_rejects_non_json():
    with pytest.raises(AnnotationInvalid):
        parse_annotation("不是 JSON")
