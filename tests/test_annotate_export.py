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


def test_export_includes_place_metadata(ctx, tmp_path):
    ctx.conn.execute(
        "insert into place(id,canonical_name) values('pl:yan','鄢')")
    ctx.conn.execute(
        "insert into place_name(place_id,name,name_type) "
        "values('pl:yan','鄢','ancient')")
    ctx.conn.execute(
        "insert into place_location(place_id,lat,lon) "
        "values('pl:yan',34.1,114.2)")
    ctx.conn.commit()

    counts = export_knowledge(ctx.conn, tmp_path / "knowledge")
    assert counts["places"] == 1
    assert counts["place_names"] >= 1
    assert counts["place_locations"] == 1
