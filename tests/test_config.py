from pathlib import Path

from xqdb.config import load_config


def test_load_config_defaults(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.data_dir == tmp_path / "data"
    assert cfg.db_path == tmp_path / "data" / "xq_index.db"
    assert cfg.corpus_dir == tmp_path / "data" / "corpus"


def test_load_config_overrides(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text(
        "db_path: custom/index.db\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.db_path == tmp_path / "custom" / "index.db"
