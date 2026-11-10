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
                force: bool = False) -> Iterator[Chunk]:
    skip: set[str] = set()
    if only_unannotated and not force:
        skip = {
            row[0] for row in conn.execute(
                "select section_id from annotation_state where status = 'ok'")
        }

    current_sid: str | None = None
    ids: list[str] = []
    parts: list[str] = []
    size = 0
    ordinal = 0

    for row in conn.execute(
            "select section_id, id, text from passage "
            "order by section_id, idx"):
        sid = row["section_id"]
        if sid != current_sid:
            if ids:
                ordinal += 1
                yield _make(current_sid, ordinal, ids, parts)
            current_sid = sid
            ids, parts, size, ordinal = [], [], 0, 0
            if sid in skip:
                continue
        if sid in skip:
            continue

        text = row["text"] or ""
        if ids and size + len(text) > max_chars:
            ordinal += 1
            yield _make(current_sid, ordinal, ids, parts)
            ids, parts, size = [], [], 0

        ids.append(row["id"])
        parts.append(text)
        size += len(text)

    if ids:
        ordinal += 1
        yield _make(current_sid, ordinal, ids, parts)
