from xqdb.tools.knowledge import entity_lookup, timeline


def test_entity_lookup_known_and_unknown(ctx):
    ctx.conn.execute(
        "insert into entity(id,type,name,name_alt) "
        "values('ent:person:zhuang','person','郑庄公','[\"寤生\"]')")
    ctx.conn.commit()
    known = entity_lookup(ctx, "郑庄公")
    assert known["found"] is True
    assert known["entity"]["id"] == "ent:person:zhuang"
    assert entity_lookup(ctx, "不存在")["found"] is False


def test_timeline_returns_interval_and_citation(ctx):
    ctx.conn.execute(
        "insert into passage_time"
        "(passage_id,year_start,year_end,confidence,basis) "
        "values('p:z:1:001',-770,-750,'high','王年表')")
    ctx.conn.commit()
    rows = timeline(ctx, -760, -755)
    assert rows[0]["passage_id"] == "p:z:1:001"
    assert rows[0]["year_start"] == -770 and rows[0]["confidence"] == "high"
