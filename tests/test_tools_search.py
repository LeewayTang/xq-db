import json

from xqdb.tools.search import search_hybrid, search_keyword, search_semantic


def test_search_returns_citation_fields(ctx):
    hits = search_keyword(ctx, "郑伯克段")
    assert hits[0]["passage_id"] == "p:z:1:001"
    assert {"work", "section", "text", "score"} <= set(hits[0])


def test_results_are_json_serializable(ctx):
    json.dumps(search_keyword(ctx, "郑伯克段"), ensure_ascii=False)


def test_empty_query_returns_empty_list(ctx):
    assert search_keyword(ctx, "   ") == []


def test_semantic_without_embedder_is_explicit(ctx):
    result = search_semantic(ctx, "礼")
    assert result == {"results": [], "semantic_available": False}


def test_hybrid_falls_back_to_keyword(ctx):
    result = search_hybrid(ctx, "郑伯克段")
    assert result["mode"] == "keyword_fallback"
    assert result["results"][0]["passage_id"] == "p:z:1:001"


def test_filters_by_relevance(ctx):
    ctx.conn.execute("update work set relevance = 'core' where id = 'w:z'")
    ctx.conn.commit()
    assert search_keyword(ctx, "郑伯克段", relevance="core")
    assert search_keyword(ctx, "郑伯克段", relevance="irrelevant") == []
