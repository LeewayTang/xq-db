from xqdb.tools.corpus import corpus_stats, get_passage, get_work, list_works


def test_get_passage_includes_neighbors(ctx):
    ctx.conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:1:002','s:z:1',2,'夏五月','夏五月',3)")
    ctx.conn.commit()
    result = get_passage(ctx, "p:z:1:001")
    assert result["work"] == "春秋左传" and result["section"] == "隐公元年"
    assert result["after"][0]["passage_id"] == "p:z:1:002"


def test_get_passage_missing_returns_error(ctx):
    assert get_passage(ctx, "p:none")["error"] == "passage not found"


def test_get_work_lists_sections(ctx):
    result = get_work(ctx, "w:z")
    assert result["title"] == "春秋左传"
    assert result["sections"][0]["title"] == "隐公元年"


def test_get_work_missing_returns_error(ctx):
    assert get_work(ctx, "w:none")["error"] == "work not found"


def test_list_works_and_stats(ctx):
    assert list_works(ctx)[0]["id"] == "w:z"
    stats = corpus_stats(ctx)
    assert stats["works"] == 1 and stats["passages"] == 1
