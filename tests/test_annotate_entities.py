from xqdb.annotate.chunk import Chunk
from xqdb.annotate.entities import persist_entities, persist_relations


def _chunk():
    return Chunk("s:z:1#001", "s:z:1", ("p:z:1:001",), "郑伯克段于鄢", 6)


def test_entities_and_mentions_written(ctx):
    counts = persist_entities(ctx.conn, _chunk(), {"entities": [
        {"passage_id": "p:z:1:001", "type": "person", "name": "郑庄公",
         "name_alt": ["寤生"], "evidence": "郑伯", "confidence": 0.9}]})
    assert counts["entities"] == 1 and counts["mentions"] == 1
    row = ctx.conn.execute("select id, name_alt from entity").fetchone()
    assert row["id"] == "ent:person:zheng-zhuang-gong"


def test_relations_link_existing_entities(ctx):
    persist_entities(ctx.conn, _chunk(), {"entities": [
        {"passage_id": "p:z:1:001", "type": "person", "name": "郑庄公"},
        {"passage_id": "p:z:1:001", "type": "person", "name": "共叔段"}]})
    n = persist_relations(ctx.conn, _chunk(), {"relations": [
        {"src_name": "郑庄公", "dst_name": "共叔段", "kind": "兄弟",
         "passage_id": "p:z:1:001", "evidence": "郑伯克段", "confidence": 0.8}]})
    assert n == 1
    row = ctx.conn.execute(
        "select src_entity, dst_entity, kind from relation").fetchone()
    assert row["kind"] == "兄弟"


def test_relation_to_unknown_name_creates_stub(ctx):
    n = persist_relations(ctx.conn, _chunk(), {"relations": [
        {"src_name": "甲", "dst_name": "乙", "kind": "x",
         "passage_id": "p:z:1:001", "evidence": "e"}]})
    assert n == 1
    assert ctx.conn.execute("select count(*) from entity").fetchone()[0] == 2
