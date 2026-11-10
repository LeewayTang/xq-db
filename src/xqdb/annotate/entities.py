import json

from ..normalize.ids import slugify_title


def entity_id(type: str, name: str) -> str:
    return f"ent:{type}:{slugify_title(name)}"


def upsert_entity(conn, item: dict) -> str:
    eid = entity_id(item["type"], item["name"])
    alts = item.get("name_alt") or []
    name_alt = json.dumps(alts, ensure_ascii=False) if alts else None
    conn.execute(
        """
        insert into entity(id, type, name, name_alt, description, era)
        values (?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
            name_alt = coalesce(excluded.name_alt, entity.name_alt),
            description = coalesce(excluded.description, entity.description)
        """,
        (eid, item["type"], item["name"], name_alt,
         item.get("description"), item.get("era")),
    )
    return eid


def resolve_or_create(conn, name: str, type: str = "unknown") -> str:
    row = conn.execute(
        "select id from entity where name = ? "
        "or (name_alt is not null and name_alt like ?) limit 1",
        (name, f'%"{name}"%'),
    ).fetchone()
    if row is not None:
        return row["id"]
    eid = entity_id(type, name)
    upsert_entity(conn, {"type": type, "name": name})
    return eid


def _delete_for_passages(conn, table: str, column: str,
                         passage_ids: tuple[str, ...]) -> None:
    if not passage_ids:
        return
    placeholders = ", ".join("?" for _ in passage_ids)
    conn.execute(
        f"delete from {table} where {column} in ({placeholders})",
        list(passage_ids),
    )


def persist_entities(conn, chunk, payload: dict) -> dict[str, int]:
    _delete_for_passages(conn, "mention", "passage_id", chunk.passage_ids)

    entities: set[str] = set()
    mentions = rejected = 0
    for item in payload.get("entities", []):
        passage_id = item.get("passage_id")
        if passage_id not in chunk.passage_ids:
            rejected += 1
            continue
        eid = upsert_entity(conn, item)
        entities.add(eid)
        conn.execute(
            "insert into mention"
            "(passage_id, entity_id, surface, role, confidence) "
            "values (?, ?, ?, ?, ?)",
            (passage_id, eid, item.get("evidence") or item["name"],
             item.get("type"), item.get("confidence")),
        )
        mentions += 1

    return {"entities": len(entities), "mentions": mentions,
            "rejected": rejected}


def persist_relations(conn, chunk, payload: dict) -> int:
    _delete_for_passages(
        conn, "relation", "evidence_passage_id", chunk.passage_ids)

    written = 0
    for item in payload.get("relations", []):
        passage_id = item.get("passage_id")
        if passage_id not in chunk.passage_ids:
            continue
        src = resolve_or_create(conn, item["src_name"])
        dst = resolve_or_create(conn, item["dst_name"])
        conn.execute(
            "insert into relation"
            "(src_entity, dst_entity, kind, evidence_passage_id) "
            "values (?, ?, ?, ?)",
            (src, dst, item["kind"], passage_id),
        )
        written += 1
    return written
