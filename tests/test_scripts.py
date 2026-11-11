import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_context_usage_script(tmp_path):
    cwd = tmp_path / "xq_db"
    cwd.mkdir()
    slug = str(cwd).replace("/", "-").replace("_", "-")
    project = tmp_path / "projects" / slug
    project.mkdir(parents=True)
    (project / "session.jsonl").write_text(
        json.dumps({
            "isSidechain": False,
            "message": {
                "model": "m",
                "usage": {
                    "input_tokens": 10,
                    "cache_read_input_tokens": 20,
                    "cache_creation_input_tokens": 10,
                    "output_tokens": 10,
                },
            },
        }) + "\n",
        encoding="utf-8",
    )

    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(tmp_path))
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "context-usage.py"),
         "--cwd", str(cwd), "--window", "100", "--json"],
        capture_output=True, text=True, env=env, check=True)
    data = json.loads(result.stdout)
    assert data["percent"] == 50.0
    assert data["tokens"]["used"] == 50


def test_handoff_dry_run():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "handoff.py"),
         "new", "test-slug", "--dry-run"],
        capture_output=True, text=True, check=True)
    assert "would write" in result.stdout


def test_handoff_template_exists():
    assert (ROOT / "docs" / "superpowers" / "handoffs"
            / "HANDOFF-TEMPLATE.md").exists()
