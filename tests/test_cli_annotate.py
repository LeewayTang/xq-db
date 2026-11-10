import shutil
from pathlib import Path

from xqdb.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _with_agents(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    shutil.copytree(ROOT / "schemas" / "agents", tmp_path / "schemas" / "agents")
    return tmp_path


def test_annotate_dry_run(tmp_path, capsys):
    root = _with_agents(tmp_path)
    assert main(["--root", str(root), "annotate", "run",
                 "--role", "annotator", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "chunk" in out


def test_annotate_export_without_data(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "annotate", "export"]) == 0
    assert (tmp_path / "data" / "knowledge" / "entities.jsonl").exists()


def test_review_llm_dry_run(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "review", "--llm", "--dry-run"]) == 0
    assert "would review" in capsys.readouterr().out
