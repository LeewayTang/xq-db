from dataclasses import dataclass

from ..normalize.simplify import to_simplified


@dataclass(frozen=True)
class Hit:
    passage_id: str
    work: str
    section: str
    text: str
    score: float


def rebuild_fts(conn) -> int:
    rows = conn.execute("select id, text_norm from passage").fetchall()
    conn.execute("delete from passage_fts")
    conn.executemany(
        "insert into passage_fts(passage_id, text_norm) values (?, ?)",
        [(row["id"], row["text_norm"]) for row in rows],
    )
    conn.commit()
    return len(rows)


def _placeholders(values) -> str:
    return ", ".join("?" for _ in values)


def _rows_to_hits(rows, limit: int) -> list[Hit]:
    hits: list[Hit] = []
    seen: set[str] = set()
    for row in rows:
        work_id = row["work_id"]
        if work_id in seen:
            continue
        seen.add(work_id)
        hits.append(Hit(
            passage_id=row["passage_id"],
            work=row["work"],
            section=row["section"],
            text=row["text"],
            score=float(row["score"]),
        ))
        if len(hits) >= limit:
            break
    return hits


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
        sql = f"""
            with hits as (
                select p.id as passage_id, w.title as work,
                       s.title as section, p.text as text, 0.0 as score,
                       e.work_id as work_id,
                       case e.quality_grade
                           when 'A' then 0 when 'B' then 1
                           when 'C' then 2 when 'Q' then 3 else 4 end
                           as grade_rank
                from passage p
                join section s on s.id = p.section_id
                join edition e on e.id = s.edition_id
                join work w on w.id = e.work_id
                where p.text_norm like ?
                  and e.quality_grade in ({_placeholders(grades)})
            ), ranked as (
                select *, row_number() over (
                    partition by work_id
                    order by grade_rank, passage_id) as rn
                from hits
            )
            select passage_id, work, section, text, score, work_id
            from ranked where rn = 1
            order by grade_rank, passage_id
            limit ?
        """
        params = [f"%{query}%", *grades, limit]
    else:
        match = '"' + query.replace('"', '""') + '"'
        sql = f"""
            with hits as (
                select p.id as passage_id, w.title as work,
                       s.title as section, p.text as text,
                       bm25(passage_fts) as score, e.work_id as work_id,
                       case e.quality_grade
                           when 'A' then 0 when 'B' then 1
                           when 'C' then 2 when 'Q' then 3 else 4 end
                           as grade_rank
                from passage_fts
                join passage p on p.id = passage_fts.passage_id
                join section s on s.id = p.section_id
                join edition e on e.id = s.edition_id
                join work w on w.id = e.work_id
                where passage_fts match ?
                  and e.quality_grade in ({_placeholders(grades)})
            ), ranked as (
                select *, row_number() over (
                    partition by work_id
                    order by grade_rank, score, passage_id) as rn
                from hits
            )
            select passage_id, work, section, text, score, work_id
            from ranked where rn = 1
            order by grade_rank, score
            limit ?
        """
        params = [match, *grades, limit]

    return _rows_to_hits(conn.execute(sql, params).fetchall(), limit)
