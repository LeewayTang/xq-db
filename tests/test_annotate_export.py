import json

from xqdb.annotate.export import export_knowledge


def test_export_writes_jsonl(ctx, tmp_path):
    ctx.conn.execute("insert into entity(id,type,name) values('ent:person:a','person','甲')")
    ctx.conn.execute("insert into mention(passage_id,entity_id,surface) "
                     "values('p:z:1:001','ent:person:a','甲')")
    ctx.conn.commit()
    counts = export_knowledge(ctx.conn, tmp_path / "knowledge")
    assert counts["entities"] == 1 and counts["mentions"] == 1
    lines = (tmp_path / "knowledge" / "entities.jsonl").read_text("utf-8").splitlines()
    assert json.loads(lines[0])["id"] == "ent:person:a"
