import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from ..normalize.simplify import to_simplified


@dataclass(frozen=True)
class Hit:
    passage_id: str
    work: str
    section: str
    text: str
    score: float
    work_id: str = ""


CHUNK_CHARS = 100_000
BATCH_CHARS = 2_000_000


def _write_batch(conn, batch: list[tuple[str, str, str]]) -> None:
    conn.executemany(
        "insert into section_fts(chunk_key, section_id, text_norm) "
        "values (?, ?, ?)",
        batch,
    )
    conn.commit()


def _iter_sections(conn):
    """Yield section text without holding a read cursor across commits.

    A single streaming cursor over 20M passages keeps a read snapshot open,
    which prevents WAL checkpointing while batches are committed. Fetching
    one section at a time releases the snapshot before each write.
    """
    section_ids = [
        row["id"] for row in conn.execute("select id from section order by id")
    ]
    for section_id in section_ids:
        rows = conn.execute(
            "select text_norm from passage where section_id = ? order by idx",
            (section_id,),
        ).fetchall()
        if rows:
            yield section_id, "\n".join(row["text_norm"] for row in rows)


def rebuild_fts(conn, *, batch_size: int = 1000,
                incremental: bool = False,
                state_only: bool = False) -> int:
    """Index one row per section; passages are resolved after matching.

    With incremental=True, only sections whose text hash changed are
    re-indexed. This keeps adding a few sources from rewriting the 4.9 GB
    section text.
    """
    if incremental:
        known = {
            row["section_id"]: row["text_hash"]
            for row in conn.execute(
                "select section_id, text_hash from section_index_state")
        }
    else:
        if not state_only:
            conn.execute("delete from section_fts")
        conn.execute("delete from section_index_state")
        conn.commit()
        known = None

    now = datetime.now(UTC).isoformat()
    count = 0
    seen: set[str] = set()
    batch: list[tuple[str, str, str]] = []
    batch_chars = 0

    for section_id, text in _iter_sections(conn):
        seen.add(section_id)
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if known is not None and known.get(section_id) == digest:
            continue

        if state_only:
            conn.execute(
                "insert into section_index_state"
                "(section_id, text_hash, indexed_at) values (?, ?, ?) "
                "on conflict(section_id) do update set "
                "text_hash = excluded.text_hash, "
                "indexed_at = excluded.indexed_at",
                (section_id, digest, now),
            )
            count += 1
            continue

        if known is not None:
            conn.execute(
                "delete from section_fts where section_id = ?", (section_id,))
        chunks = [
            text[index:index + CHUNK_CHARS]
            for index in range(0, len(text), CHUNK_CHARS)
        ] or [""]
        for index, chunk in enumerate(chunks):
            batch.append(
                (f"{section_id}#{index:03d}", section_id, chunk))
            batch_chars += len(chunk)
        conn.execute(
            "insert into section_index_state"
            "(section_id, text_hash, indexed_at) values (?, ?, ?) "
            "on conflict(section_id) do update set "
            "text_hash = excluded.text_hash, indexed_at = excluded.indexed_at",
            (section_id, digest, now),
        )
        count += 1
        if len(batch) >= batch_size or batch_chars >= BATCH_CHARS:
            _write_batch(conn, batch)
            batch.clear()
            batch_chars = 0

    if batch:
        _write_batch(conn, batch)

    if known is not None:
        stale = [section_id for section_id in known if section_id not in seen]
        if stale:
            conn.executemany(
                "delete from section_fts where section_id = ?",
                [(section_id,) for section_id in stale])
            conn.executemany(
                "delete from section_index_state where section_id = ?",
                [(section_id,) for section_id in stale])
            conn.commit()

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
