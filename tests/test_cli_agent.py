import shutil
from pathlib import Path

from xqdb.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _with_agents(tmp_path):
    shutil.copytree(FIXTURES / "agents", tmp_path / "agents")
    shutil.copytree(
        FIXTURES / "schemas" / "agents", tmp_path / "schemas" / "agents")
    return tmp_path


def test_tools_list(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "tools"]) == 0
    out = capsys.readouterr().out
    assert "search_keyword" in out and "ingest_run" not in out


def test_agent_roles(tmp_path, capsys):
    root = _with_agents(tmp_path)
    assert main(["--root", str(root), "agent", "roles"]) == 0
    out = capsys.readouterr().out
    assert "researcher" in out and "muse" in out


def test_agent_run_dry_run(tmp_path, capsys):
    root = _with_agents(tmp_path)
    assert main(["--root", str(root), "agent", "run", "--role", "researcher",
                 "--task", "查郑伯克段", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "budget" in out and "search_keyword" in out


def test_agent_run_without_key_reports_clearly(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    root = _with_agents(tmp_path)
    assert main(["--root", str(root), "agent", "run",
                 "--role", "researcher", "--task", "x"]) == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().out
