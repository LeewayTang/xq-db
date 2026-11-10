def get_passage(ctx, passage_id: str, context: int = 1) -> dict:
    row = ctx.conn.execute(
        """
        select p.id as passage_id, p.idx, p.text, p.char_count,
               s.id as section_id, s.title as section,
               e.id as edition_id, e.work_id, w.title as work
        from passage p
        join section s on s.id = p.section_id
        join edition e on e.id = s.edition_id
        join work w on w.id = e.work_id
        where p.id = ?
        """,
        (passage_id,),
    ).fetchone()
    if row is None:
        return {"error": "passage not found", "passage_id": passage_id}

    before = ctx.conn.execute(
        "select id as passage_id, idx, text from passage "
        "where section_id = ? and idx < ? order by idx desc limit ?",
        (row["section_id"], row["idx"], context),
    ).fetchall()
    after = ctx.conn.execute(
        "select id as passage_id, idx, text from passage "
        "where section_id = ? and idx > ? order by idx asc limit ?",
        (row["section_id"], row["idx"], context),
    ).fetchall()

    return {
        "passage": {
            "passage_id": row["passage_id"],
            "idx": row["idx"],
            "text": row["text"],
            "char_count": row["char_count"],
        },
        "before": [dict(item) for item in reversed(before)],
        "after": [dict(item) for item in after],
        "work": row["work"],
        "section": row["section"],
        "work_id": row["work_id"],
        "edition_id": row["edition_id"],
    }


def get_work(ctx, work_id: str, include_text: bool = False,
             max_passages: int = 2000) -> dict:
    work = ctx.conn.execute(
        "select id, title, author, era, genre, relevance "
        "from work where id = ?",
        (work_id,),
    ).fetchone()
    if work is None:
        return {"error": "work not found", "work_id": work_id}

    editions = [
        dict(row) for row in ctx.conn.execute(
            "select id, source_id, title_in_source, char_count, "
            "quality_grade, review_status from edition "
            "where work_id = ? order by id",
            (work_id,),
        )
    ]

    total_passages = 0
    remaining = max_passages
    sections = []
    for edition in editions:
        rows = ctx.conn.execute(
            "select id, idx, title, level from section "
            "where edition_id = ? order by idx",
            (edition["id"],),
        ).fetchall()
        for section in rows:
            item = dict(section)
            if include_text:
                count = ctx.conn.execute(
                    "select count(*) from passage where section_id = ?",
                    (section["id"],),
                ).fetchone()[0]
                total_passages += count
                if remaining > 0:
                    passages = ctx.conn.execute(
                        "select id, idx, text from passage "
                        "where section_id = ? order by idx limit ?",
                        (section["id"], remaining),
                    ).fetchall()
                    item["passages"] = [dict(p) for p in passages]
                    remaining -= len(passages)
            sections.append(item)

    return {
        "id": work["id"],
        "title": work["title"],
        "author": work["author"],
        "era": work["era"],
        "genre": work["genre"],
        "relevance": work["relevance"],
        "editions": editions,
        "sections": sections,
        "truncated": include_text and total_passages > max_passages,
    }


def list_works(ctx, *, era=None, genre=None, relevance=None,
               limit: int = 50, offset: int = 0) -> list[dict]:
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

    where = ("where " + " and ".join(clauses)) if clauses else ""
    params.extend([limit, offset])
    rows = ctx.conn.execute(
        "select id, title, author, era, genre, relevance from work "
        f"{where} order by id limit ? offset ?",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def corpus_stats(ctx) -> dict:
    def count(table: str) -> int:
        return ctx.conn.execute(f"select count(*) from {table}").fetchone()[0]

    grades = {
        (row[0] or "unknown"): row[1]
        for row in ctx.conn.execute(
            "select quality_grade, count(*) from edition "
            "group by quality_grade order by quality_grade")
    }
    version = ctx.conn.execute(
        "select value from index_meta where key = 'schema_version'"
    ).fetchone()

    return {
        "works": count("work"),
        "editions": count("edition"),
        "sections": count("section"),
        "passages": count("passage"),
        "grades": grades,
        "schema_version": version[0] if version else None,
    }
