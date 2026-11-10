import json
from pathlib import Path

from xqdb.annotate.chunk import Chunk
from xqdb.annotate.persist import persist_annotation, record_state

FIXTURE = Path("tests/fixtures/annotations/zuozhuan.json")


def test_persist_is_idempotent(ctx):
    chunk = Chunk("s:z:1#001", "s:z:1", ("p:z:1:001",), "郑伯克段于鄢", 6)
    payload = json.loads(FIXTURE.read_text("utf-8"))
    first = persist_annotation(ctx.conn, chunk, payload, model="fake")
    second = persist_annotation(ctx.conn, chunk, payload, model="fake")
    assert first == second
    for table in ("mention", "passage_time", "passage_place", "passage_tag"):
        assert ctx.conn.execute(f"select count(*) from {table}").fetchone()[0] > 0


def test_out_of_chunk_passage_is_rejected(ctx):
    chunk = Chunk("s:z:1#001", "s:z:1", ("p:z:1:001",), "郑伯克段于鄢", 6)
    payload = {"entities": [{"passage_id": "p:other", "type": "person",
                             "name": "某人", "evidence": "x"}]}
    counts = persist_annotation(ctx.conn, chunk, payload)
    assert counts["rejected"] == 1
    assert ctx.conn.execute("select count(*) from mention").fetchone()[0] == 0


def test_record_state_upserts(ctx):
    record_state(ctx.conn, "s:z:1#001", "s:z:1", "ok", model="fake")
    record_state(ctx.conn, "s:z:1#001", "s:z:1", "error", attempts=2, error="bad")
    row = ctx.conn.execute("select status, attempts from annotation_state").fetchone()
    assert row["status"] == "error" and row["attempts"] == 2
