import json
from pathlib import Path

EXPORTS = {
    "entities": ("entity", "id"),
    "mentions": ("mention", "id"),
    "relations": ("relation", "id"),
    "events": ("event", "id"),
    "event_participants": ("event_participant", "event_id, entity_id"),
    "passage_times": ("passage_time", "id"),
    "passage_places": ("passage_place", "passage_id, place_id, role"),
    "places": ("place", "id"),
    "place_names": ("place_name", "id"),
    "place_locations": ("place_location", "id"),
    "place_hierarchy": ("place_hierarchy", "child_id, parent_id, relation"),
    "tags": ("tag", "id"),
    "passage_tags": ("passage_tag", "passage_id, tag_id"),
}


def export_knowledge(conn, out_dir: Path) -> dict[str, int]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for name, (table, order_by) in EXPORTS.items():
        rows = conn.execute(
            f"select * from {table} order by {order_by}").fetchall()
        with (out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(
                    json.dumps(dict(row), ensure_ascii=False) + "\n")
        counts[name] = len(rows)
    return counts
