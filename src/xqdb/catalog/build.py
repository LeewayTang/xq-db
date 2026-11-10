import json
from pathlib import Path


def build_index_jsonl(conn, out: Path) -> int:
    rows = conn.execute(
        """
        select w.id, w.title, w.author, w.era, w.genre, w.relevance,
               count(e.id) as editions,
               min(case e.quality_grade
                       when 'A' then 0 when 'B' then 1
                       when 'C' then 2 when 'Q' then 3 else 4 end) as best_rank
        from work w
        left join edition e on e.work_id = w.id
        group by w.id
        order by w.id
        """
    ).fetchall()

    grades = ["A", "B", "C", "Q", None]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            item = dict(row)
            item["best_grade"] = grades[min(item.pop("best_rank"), 4)]
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(rows)
