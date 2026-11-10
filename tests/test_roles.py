from pathlib import Path

import pytest

from xqdb.harness.roles import load_role, load_roles

AGENTS = Path(__file__).parent / "fixtures" / "agents"


def test_loads_all_six_roles():
    roles = load_roles(AGENTS)
    assert {"librarian", "curator", "reviewer",
            "annotator", "researcher", "muse"} <= set(roles)


def test_researcher_is_read_only():
    role = load_role(AGENTS, "researcher")
    assert "note_add" not in role.tools
    assert role.prompt.strip()


def test_unknown_tool_rejected(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "bad.md").write_text(
        "---\nrole: bad\ntools: [no_such_tool]\n"
        "output_schema: bad.schema.json\n"
        "budget: {max_tokens: 100, max_tool_calls: 1, max_cost_usd: 0.1}\n"
        "---\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_roles(tmp_path / "agents")


def _admin_role(tmp_path, allow_admin: bool):
    (tmp_path / "agents").mkdir()
    (tmp_path / "schemas" / "agents").mkdir(parents=True)
    (tmp_path / "schemas" / "agents" / "x.schema.json").write_text(
        "{\"type\": \"object\"}", encoding="utf-8")
    flag = "\nallow_admin: true" if allow_admin else ""
    (tmp_path / "agents" / "x.md").write_text(
        "---\nrole: x\ntools: [ingest_run]\n"
        "output_schema: x.schema.json\n"
        "budget: {max_tokens: 100, max_tool_calls: 1, max_cost_usd: 0.1}"
        f"{flag}\n---\n", encoding="utf-8")


def test_admin_tool_rejected_by_default(tmp_path):
    _admin_role(tmp_path, allow_admin=False)
    with pytest.raises(ValueError):
        load_roles(tmp_path / "agents")


def test_admin_tool_allowed_with_flag(tmp_path):
    _admin_role(tmp_path, allow_admin=True)
    role = load_role(tmp_path / "agents", "x")
    assert role.tools == ("ingest_run",)
