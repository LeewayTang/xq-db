import hashlib

from ..normalize.ids import slugify_title
from ..space.place import add_location, add_name, upsert_place
from .entities import _delete_for_passages, resolve_or_create


def _event_id(name: str, passage_id: str) -> str:
    digest = hashlib.sha1((name + passage_id).encode("utf-8")).hexdigest()[:6]
    return f"evt:{slugify_title(name)}:{digest}"


def _place_id(name: str) -> str:
    return f"pl:{slugify_title(name)}"


def _ensure_place(conn, name: str, type: str = "place") -> str:
    place_id = _place_id(name)
    upsert_place(conn, place_id, name, type)
    return place_id


def _add_name_once(conn, place_id: str, name: str, name_type: str) -> None:
    exists = conn.execute(
        "select 1 from place_name where place_id = ? and name = ?",
        (place_id, name),
    ).fetchone()
    if exists is None:
        add_name(conn, place_id, name, name_type)


def persist_events(conn, chunk, payload: dict) -> int:
    _delete_for_passages(conn, "passage_time", "passage_id", chunk.passage_ids)

    written = 0
    for item in payload.get("events", []):
        passage_id = item.get("passage_id")
        if passage_id not in chunk.passage_ids:
            continue

        event_id = _event_id(item["name"], passage_id)
        conn.execute("delete from event where id = ?", (event_id,))
        conn.execute(
            "insert into event"
            "(id, name, date_text, year_start, year_end, confidence, basis) "
            "values (?, ?, ?, ?, ?, ?, ?)",
            (event_id, item["name"], item.get("date_text"),
             item.get("year_start"), item.get("year_end"),
             item.get("confidence"), item.get("basis")),
        )
        for participant in item.get("participants", []):
            entity = resolve_or_create(conn, participant)
            conn.execute(
                "insert or ignore into event_participant"
                "(event_id, entity_id, role) values (?, ?, 'participant')",
                (event_id, entity),
            )

        if item.get("year_start") is not None and item.get("year_end") is not None:
            conn.execute(
                "insert into passage_time"
                "(passage_id, year_start, year_end, confidence, basis) "
                "values (?, ?, ?, ?, ?)",
                (passage_id, item["year_start"], item["year_end"],
                 item.get("confidence"), item.get("basis")),
            )

        place_name = item.get("place_name")
        if place_name:
            place_id = _ensure_place(conn, place_name)
            conn.execute(
                "insert or replace into passage_place"
                "(passage_id, place_id, role, confidence) "
                "values (?, ?, 'event', ?)",
                (passage_id, place_id, item.get("confidence")),
            )
        written += 1
    return written


def persist_places(conn, chunk, payload: dict) -> int:
    _delete_for_passages(conn, "passage_place", "passage_id", chunk.passage_ids)

    written = 0
    for item in payload.get("places", []):
        passage_id = item.get("passage_id")
        if passage_id not in chunk.passage_ids:
            continue

        place_id = _ensure_place(conn, item["name"])
        _add_name_once(conn, place_id, item["name"], "ancient")

        modern_name = item.get("modern_name")
        if modern_name:
            _add_name_once(conn, place_id, modern_name, "modern")

        lat, lon = item.get("lat"), item.get("lon")
        if lat is not None and lon is not None:
            exists = conn.execute(
                "select 1 from place_location "
                "where place_id = ? and lat = ? and lon = ?",
                (place_id, lat, lon),
            ).fetchone()
            if exists is None:
                add_location(
                    conn, place_id, lat, lon,
                    confidence=item.get("confidence", 0.5))

        conn.execute(
            "insert or replace into passage_place"
            "(passage_id, place_id, role, confidence) values (?, ?, ?, ?)",
            (passage_id, place_id, item.get("role", "mention"),
             item.get("confidence")),
        )
        written += 1
    return written


def persist_tags(conn, chunk, payload: dict) -> int:
    _delete_for_passages(conn, "passage_tag", "passage_id", chunk.passage_ids)

    written = 0
    for item in payload.get("tags", []):
        passage_id = item.get("passage_id")
        if passage_id not in chunk.passage_ids:
            continue

        category = item.get("category") or "主题"
        tag_id = f"tag:{slugify_title(category)}:{slugify_title(item['name'])}"
        conn.execute(
            "insert or ignore into tag(id, name, category) values (?, ?, ?)",
            (tag_id, item["name"], category),
        )
        conn.execute(
            "insert or replace into passage_tag"
            "(passage_id, tag_id, confidence) values (?, ?, ?)",
            (passage_id, tag_id, item.get("confidence")),
        )
        written += 1
    return written
