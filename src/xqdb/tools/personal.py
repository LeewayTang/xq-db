import sqlite3
from datetime import UTC, datetime


def note_add(ctx, target_type: str, target_id: str, body: str) -> dict:
    created_at = datetime.now(UTC).isoformat()
    with ctx.conn:
        cursor = ctx.conn.execute(
            "insert into note(target_type, target_id, body, created_at) "
            "values (?, ?, ?, ?)",
            (target_type, target_id, body, created_at),
        )
    return {
        "id": cursor.lastrowid,
        "target_type": target_type,
        "target_id": target_id,
        "body": body,
        "created_at": created_at,
    }


def note_search(ctx, query: str | None = None,
                target_id: str | None = None, limit: int = 20) -> list[dict]:
    clauses = []
    params: list = []
    if query:
        clauses.append("body like ?")
        params.append(f"%{query}%")
    if target_id:
        clauses.append("target_id = ?")
        params.append(target_id)
    where = ("where " + " and ".join(clauses)) if clauses else ""
    params.append(limit)

    rows = ctx.conn.execute(
        "select id, target_type, target_id, body, created_at from note "
        f"{where} order by created_at desc, id desc limit ?",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def seed_add(ctx, title: str, premise: str,
             passage_ids: tuple[str, ...] = ()) -> dict:
    created_at = datetime.now(UTC).isoformat()
    seed_id = None
    try:
        with ctx.conn:
            cursor = ctx.conn.execute(
                "insert into story_seed(title, premise, status, created_at) "
                "values (?, ?, 'new', ?)",
                (title, premise, created_at),
            )
            seed_id = cursor.lastrowid
            for passage_id in passage_ids:
                ctx.conn.execute(
                    "insert into seed_passage(seed_id, passage_id) "
                    "values (?, ?)",
                    (seed_id, passage_id),
                )
    except sqlite3.IntegrityError:
        return {"error": "invalid passage_id", "passage_id": passage_id}

    return {
        "id": seed_id,
        "title": title,
        "premise": premise,
        "status": "new",
        "passages": list(passage_ids),
        "created_at": created_at,
    }


def seed_list(ctx, status: str | None = None, limit: int = 20) -> list[dict]:
    params: list = []
    where = ""
    if status:
        where = "where status = ?"
        params.append(status)
    params.append(limit)

    rows = ctx.conn.execute(
        "select id, title, premise, status, created_at from story_seed "
        f"{where} order by id desc limit ?",
        params,
    ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["passages"] = [
            item_row[0] for item_row in ctx.conn.execute(
                "select passage_id from seed_passage "
                "where seed_id = ? order by passage_id",
                (row["id"],),
            )
        ]
        result.append(item)
    return result
