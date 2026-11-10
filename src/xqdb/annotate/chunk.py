from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    section_id: str
    passage_ids: tuple[str, ...]
    text: str
    char_count: int


def _make(section_id: str, ordinal: int, ids: list[str],
          parts: list[str]) -> Chunk:
    return Chunk(
        chunk_id=f"{section_id}#{ordinal:03d}",
        section_id=section_id,
        passage_ids=tuple(ids),
        text="\n".join(parts),
        char_count=sum(len(part) for part in parts),
    )


def iter_chunks(conn, *, max_chars: int = 4000,
                only_unannotated: bool = False,
                force: bool = False,
                relevance: str | None = None,
                grades: tuple[str, ...] = ("A", "B", "C")) -> Iterator[Chunk]:
    done: set[str] = set()
    if only_unannotated and not force:
        done = {
            row[0] for row in conn.execute(
                "select chunk_id from annotation_state where status = 'ok'")
        }

    placeholders = ", ".join("?" for _ in grades)
    rows = conn.execute(
        f"""
        select p.section_id, p.id, p.text
        from passage p
        join section s on s.id = p.section_id
        join edition e on e.id = s.edition_id
        join work w on w.id = e.work_id
        where e.quality_grade in ({placeholders})
          and (? is null or w.relevance = ?)
        order by p.section_id, p.idx
        """,
        (*grades, relevance, relevance),
    )

    current_sid: str | None = None
    ids: list[str] = []
    parts: list[str] = []
    size = 0
    ordinal = 0

    def emit() -> Chunk:
        chunk = _make(current_sid, ordinal, ids, parts)
        return chunk

    for row in rows:
        sid = row["section_id"]
        if sid != current_sid:
            if ids:
                ordinal += 1
                chunk = emit()
                if chunk.chunk_id not in done:
                    yield chunk
            current_sid = sid
            ids, parts, size, ordinal = [], [], 0, 0

        text = row["text"] or ""
        if ids and size + len(text) > max_chars:
            ordinal += 1
            chunk = emit()
            if chunk.chunk_id not in done:
                yield chunk
            ids, parts, size = [], [], 0

        ids.append(row["id"])
        parts.append(text)
        size += len(text)

    if ids:
        ordinal += 1
        chunk = emit()
        if chunk.chunk_id not in done:
            yield chunk
