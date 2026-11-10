import sqlite3
from pathlib import Path

SCHEMA_VERSION = "1"


def _schema_path() -> Path:
    path = Path(__file__).resolve().parents[1] / "schema.sql"
    if not path.exists():
        raise FileNotFoundError(f"schema not found: {path}")
    return path


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_schema_path().read_text(encoding="utf-8"))
    columns = {row[1] for row in conn.execute("pragma table_info(event)")}
    if columns and "passage_id" not in columns:
        conn.execute(
            "alter table event add column passage_id text "
            "references passage(id)")
    conn.execute(
        "INSERT OR IGNORE INTO index_meta(key, value) VALUES (?, ?)",
        ("schema_version", SCHEMA_VERSION),
    )
    conn.commit()
