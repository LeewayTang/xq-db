from ..index.fts import Hit
from .place import haversine_km


def _dedupe(hits: list[Hit], limit: int) -> list[Hit]:
    result: list[Hit] = []
    seen: set[str] = set()
    for work_id, hit in hits:
        if work_id in seen:
            continue
        seen.add(work_id)
        result.append(hit)
        if len(result) >= limit:
            break
    return result


def passages_in_time(conn, start: int, end: int, limit: int = 20) -> list[Hit]:
    rows = conn.execute(
        """
        select p.id as passage_id, w.title as work, s.title as section,
               p.text as text, e.work_id as work_id
        from passage_time t
        join passage p on p.id = t.passage_id
        join section s on s.id = p.section_id
        join edition e on e.id = s.edition_id
        join work w on w.id = e.work_id
        where t.year_start <= ? and t.year_end >= ?
          and e.quality_grade in ('A', 'B')
        order by t.year_start
        """,
        (end, start),
    ).fetchall()
    hits = [
        (row["work_id"], Hit(
            passage_id=row["passage_id"],
            work=row["work"],
            section=row["section"],
            text=row["text"],
            score=0.0,
        ))
        for row in rows
    ]
    return _dedupe(hits, limit)


def passages_near(conn, lat: float, lon: float, radius_km: float,
                  limit: int = 20) -> list[Hit]:
    rows = conn.execute(
        """
        select p.id as passage_id, w.title as work, s.title as section,
               p.text as text, e.work_id as work_id,
               l.lat as lat, l.lon as lon
        from passage_place pp
        join place_location l on l.place_id = pp.place_id
        join passage p on p.id = pp.passage_id
        join section s on s.id = p.section_id
        join edition e on e.id = s.edition_id
        join work w on w.id = e.work_id
        where e.quality_grade in ('A', 'B')
        """
    ).fetchall()

    scored: list[tuple[float, str, Hit]] = []
    for row in rows:
        distance = haversine_km(lat, lon, row["lat"], row["lon"])
        if distance <= radius_km:
            scored.append((distance, row["work_id"], Hit(
                passage_id=row["passage_id"],
                work=row["work"],
                section=row["section"],
                text=row["text"],
                score=distance,
            )))
    scored.sort(key=lambda item: item[0])
    return _dedupe([(work_id, hit) for _, work_id, hit in scored], limit)
