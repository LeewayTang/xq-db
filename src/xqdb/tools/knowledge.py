def entity_lookup(ctx, name: str) -> dict:
    row = ctx.conn.execute(
        """
        select id, type, name, name_alt, description, era
        from entity
        where name = ? or (name_alt is not null and name_alt like ?)
        limit 1
        """,
        (name, f'%"{name}"%'),
    ).fetchone()
    if row is None:
        return {"found": False, "name": name}

    entity_id = row["id"]
    mentions = ctx.conn.execute(
        "select count(*) from mention where entity_id = ?", (entity_id,)
    ).fetchone()[0]
    relations = [
        dict(item) for item in ctx.conn.execute(
            """
            select r.kind, r.src_entity, r.dst_entity,
                   s.name as src_name, d.name as dst_name
            from relation r
            left join entity s on s.id = r.src_entity
            left join entity d on d.id = r.dst_entity
            where r.src_entity = ? or r.dst_entity = ?
            """,
            (entity_id, entity_id),
        )
    ]
    return {
        "found": True,
        "entity": dict(row),
        "mentions": mentions,
        "relations": relations,
    }


def timeline(ctx, start: int, end: int, *, entity: str | None = None,
             limit: int = 20) -> list[dict]:
    params: list = [end, start]
    entity_clause = ""
    if entity:
        found = ctx.conn.execute(
            "select id from entity where id = ? or name = ?",
            (entity, entity),
        ).fetchone()
        if found is None:
            return []
        entity_clause = (
            " and exists (select 1 from mention m "
            "where m.passage_id = p.id and m.entity_id = ?)")
        params.append(found["id"])
    params.append(limit)

    rows = ctx.conn.execute(
        f"""
        select p.id as passage_id, w.title as work, s.title as section,
               p.text as text, t.year_start, t.year_end,
               t.confidence, t.basis
        from passage_time t
        join passage p on p.id = t.passage_id
        join section s on s.id = p.section_id
        join edition e on e.id = s.edition_id
        join work w on w.id = e.work_id
        where t.year_start <= ? and t.year_end >= ?
          and e.quality_grade in ('A', 'B')
          {entity_clause}
        order by t.year_start, p.id
        limit ?
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]
