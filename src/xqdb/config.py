from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    root: Path
    config_path: Path
    data_dir: Path
    raw_dir: Path
    corpus_dir: Path
    knowledge_dir: Path
    db_path: Path


_DEFAULTS = {
    "data_dir": "data",
    "raw_dir": "data/raw",
    "corpus_dir": "data/corpus",
    "knowledge_dir": "data/knowledge",
    "db_path": "data/xq_index.db",
}


def load_config(root: Path | None = None) -> Config:
    root = Path(root if root is not None else Path.cwd()).resolve()
    config_path = root / "config" / "config.yaml"
    raw: dict = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    def resolve(key: str) -> Path:
        value = Path(raw.get(key, _DEFAULTS[key]))
        return value if value.is_absolute() else root / value

    return Config(
        root=root,
        config_path=config_path,
        data_dir=resolve("data_dir"),
        raw_dir=resolve("raw_dir"),
        corpus_dir=resolve("corpus_dir"),
        knowledge_dir=resolve("knowledge_dir"),
        db_path=resolve("db_path"),
    )
