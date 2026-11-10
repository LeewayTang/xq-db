from dataclasses import dataclass

from ..normalize.simplify import to_simplified


@dataclass(frozen=True)
class Hit:
    passage_id: str
    work: str
    section: str
    text: str
    score: float
    work_id: str = ""


def _write_batch(conn, batch: list[tuple[str, str]]) -> None:
    conn.executemany(
        "insert into section_fts(section_id, text_norm) values (?, ?)",
        batch,
    )
    conn.commit()


def rebuild_fts(conn, *, batch_size: int = 1000) -> int:
    """Index one row per section; passages are resolved after matching."""
    conn.execute("delete from section_fts")
    conn.commit()

    count = 0
    batch: list[tuple[str, str]] = []
    current: str | None = None
    parts: list[str] = []

    def flush_section() -> None:
        nonlocal count
        if current is None:
            return
        batch.append((current, "\n".join(parts)))
        count += 1

    for row in conn.execute(
            "select section_id, text_norm from passage order by section_id, idx"):
        if row["section_id"] != current:
            flush_section()
            if len(batch) >= batch_size:
                _write_batch(conn, batch)
                batch.clear()
            current = row["section_id"]
            parts = [row["text_norm"]]
        else:
            parts.append(row["text_norm"])

    flush_section()
    if batch:
        _write_batch(conn, batch)

    return count


def _placeholders(values) -> str:
    return ", ".join("?" for _ in values)


def _best_passage(conn, section_id: str, query: str):
    row = conn.execute(
        "select id, text from passage "
        "where section_id = ? and text_norm like ? order by idx limit 1",
        (section_id, f"%{query}%"),
    ).fetchone()
    if row is None:
        row = conn.execute(
            "select id, text from passage where section_id = ? "
            "order by idx limit 1",
            (section_id,),
        ).fetchone()
    return row


def search(
    conn,
    query: str,
    *,
    limit: int = 20,
    grades: tuple[str, ...] = ("A", "B"),
) -> list[Hit]:
    query = to_simplified(query).strip()
    if not query or not grades:
        return []

    if len(query) < 3:
        condition = "f.text_norm like ?"
        score = "0.0"
        params = [f"%{query}%", *grades]
    else:
        match = '"' + query.replace('"', '""') + '"'
        condition = "section_fts match ?"
        score = "bm25(section_fts)"
        params = [match, *grades]

    sql = f"""
        with hits as (
            select f.section_id, s.title as section, w.title as work,
                   e.work_id as work_id, {score} as score,
                   case e.quality_grade
                       when 'A' then 0 when 'B' then 1
                       when 'C' then 2 when 'Q' then 3 else 4 end
                       as grade_rank
            from section_fts f
            join section s on s.id = f.section_id
            join edition e on e.id = s.edition_id
            join work w on w.id = e.work_id
            where {condition}
              and e.quality_grade in ({_placeholders(grades)})
        ), ranked as (
            select *, row_number() over (
                partition by work_id
                order by grade_rank, score, section_id) as rn
            from hits
        )
        select section_id, work, section, score, work_id
        from ranked where rn = 1
        order by score, grade_rank
        limit ?
    """
    params.append(limit)

    hits: list[Hit] = []
    for row in conn.execute(sql, params).fetchall():
        passage = _best_passage(conn, row["section_id"], query)
        if passage is None:
            continue
        hits.append(Hit(
            passage_id=passage["id"],
            work=row["work"],
            section=row["section"],
            text=passage["text"],
            score=float(row["score"]),
            work_id=row["work_id"],
        ))
    return hits
