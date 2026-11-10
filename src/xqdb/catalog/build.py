import json
from pathlib import Path


def build_index_jsonl(conn, out: Path) -> int:
    rows = conn.execute(
        """
        select w.id, w.title, w.author, w.era, w.genre, w.relevance,
               count(e.id) as editions,
               max(e.quality_grade) as best_grade
        from work w
        left join edition e on e.work_id = w.id
        group by w.id
        order by w.id
        """
    ).fetchall()

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
    return len(rows)
