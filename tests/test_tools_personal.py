from xqdb.tools.personal import note_add, note_search, seed_add, seed_list


def test_note_roundtrip(ctx):
    created = note_add(ctx, "passage", "p:z:1:001", "郑伯克段的叙事很紧")
    assert created["id"] > 0
    rows = note_search(ctx, query="叙事")
    assert rows[0]["target_id"] == "p:z:1:001"


def test_seed_links_passages(ctx):
    created = seed_add(ctx, "兄弟相残", "共叔段与郑庄公", ("p:z:1:001",))
    assert created["id"] > 0
    rows = seed_list(ctx)
    assert rows[0]["title"] == "兄弟相残"
    assert rows[0]["passages"] == ["p:z:1:001"]
