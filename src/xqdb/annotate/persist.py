from datetime import UTC, datetime

from .entities import persist_entities, persist_relations
from .events import persist_events, persist_places, persist_tags


def persist_annotation(conn, chunk, payload: dict, *,
                       model: str = "unknown") -> dict[str, int]:
    with conn:
        entities = persist_entities(conn, chunk, payload)
        relations = persist_relations(conn, chunk, payload)
        events = persist_events(conn, chunk, payload)
        places = persist_places(conn, chunk, payload)
        tags = persist_tags(conn, chunk, payload)

    return {
        "entities": entities["entities"],
        "mentions": entities["mentions"],
        "relations": relations,
        "events": events,
        "places": places,
        "tags": tags,
        "rejected": entities["rejected"],
    }


def record_state(conn, chunk_id: str, section_id: str, status: str, *,
                 attempts: int = 0, error: str | None = None,
                 model: str | None = None) -> None:
    updated_at = datetime.now(UTC).isoformat()
    conn.execute(
        """
        insert into annotation_state
        (chunk_id, section_id, status, attempts, error, model, updated_at)
        values (?, ?, ?, ?, ?, ?, ?)
        on conflict(chunk_id) do update set
            section_id = excluded.section_id,
            status = excluded.status,
            attempts = excluded.attempts,
            error = excluded.error,
            model = excluded.model,
            updated_at = excluded.updated_at
        """,
        (chunk_id, section_id, status, attempts, error, model, updated_at),
    )
    conn.commit()
