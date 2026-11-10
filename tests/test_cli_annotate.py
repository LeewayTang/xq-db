import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from xqdb.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _with_agents(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    shutil.copytree(ROOT / "schemas" / "agents", tmp_path / "schemas" / "agents")
    return tmp_path


def _spend(root, cost=0.5):
    now = datetime.now(UTC)
    run_id = now.strftime("%Y%m") + "01T000000000000-a"
    directory = root / "data" / "runs" / run_id
    directory.mkdir(parents=True)
    (directory / "run.json").write_text(
        json.dumps({"run_id": run_id, "usage": {"cost_usd": cost}}),
        encoding="utf-8")


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


def test_annotate_respects_monthly_budget(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    root = _with_agents(tmp_path)
    (root / "config").mkdir()
    (root / "config" / "config.yaml").write_text(
        "agent:\n  monthly_budget_usd: 0.01\n", encoding="utf-8")
    _spend(root)

    assert main(["--root", str(root), "annotate", "run",
                 "--role", "annotator"]) == 1
    assert "monthly budget" in capsys.readouterr().out.lower()


def test_review_llm_respects_monthly_budget(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    root = _with_agents(tmp_path)
    (root / "config").mkdir()
    (root / "config" / "config.yaml").write_text(
        "agent:\n  monthly_budget_usd: 0.01\n", encoding="utf-8")
    _spend(root)

    assert main(["--root", str(root), "review", "--llm"]) == 1
    assert "monthly budget" in capsys.readouterr().out.lower()
