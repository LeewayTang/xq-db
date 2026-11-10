from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..config import Config, load_config
from ..store.db import connect, init_db


@dataclass(frozen=True)
class ToolContext:
    cfg: Config
    conn: object
    embedder: object | None = None


@contextmanager
def tool_context(root: Path | None = None):
    cfg = load_config(root)
    conn = connect(cfg.db_path)
    init_db(conn)
    try:
        yield ToolContext(cfg=cfg, conn=conn)
    finally:
        conn.close()
