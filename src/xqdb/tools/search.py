from dataclasses import asdict

from ..index.fts import Hit, search


def hit_to_dict(hit: Hit) -> dict:
    item = asdict(hit)
    item["score"] = float(item["score"])
    return item


def _allowed_work_ids(ctx, era=None, genre=None, relevance=None) -> set[str] | None:
    clauses = []
    params: list[str] = []
    if era:
        clauses.append("era = ?")
        params.append(era)
    if genre:
        clauses.append("genre = ?")
        params.append(genre)
    if relevance:
        clauses.append("relevance = ?")
        params.append(relevance)
    if not clauses:
        return None
    rows = ctx.conn.execute(
        "select id from work where " + " and ".join(clauses), params)
    return {row["id"] for row in rows}


def search_keyword(
    ctx,
    query: str,
    *,
    limit: int = 20,
    grades: tuple[str, ...] = ("A", "B"),
    era: str | None = None,
    genre: str | None = None,
    relevance: str | None = None,
) -> list[dict]:
    if not query.strip():
        return []

    hits = search(ctx.conn, query, limit=limit, grades=grades)
    allowed = _allowed_work_ids(ctx, era=era, genre=genre, relevance=relevance)
    if allowed is not None:
        hits = [hit for hit in hits if hit.work_id in allowed]
    return [hit_to_dict(hit) for hit in hits]


def search_semantic(ctx, query: str, *, k: int = 10, **filters) -> dict:
    if ctx.embedder is None:
        return {"results": [], "semantic_available": False}
    ctx.embedder.embed([query])
    return {"results": [], "semantic_available": True}


def search_hybrid(ctx, query: str, *, k: int = 10, **filters) -> dict:
    semantic = search_semantic(ctx, query, k=k, **filters)
    if not semantic["semantic_available"]:
        return {
            "results": search_keyword(ctx, query, limit=k, **filters),
            "mode": "keyword_fallback",
        }
    return {
        "results": search_keyword(ctx, query, limit=k, **filters),
        "mode": "hybrid",
    }
