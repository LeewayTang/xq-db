import json
from datetime import UTC, datetime

from xqdb.harness.config import load_agent_config
from xqdb.harness.runlog import month_to_date_cost


def test_reads_prices(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text(
        "agent:\n  model: m\n  prices:\n    m: [1.5, 2.5]\n",
        encoding="utf-8")
    cfg = load_agent_config(tmp_path)
    assert cfg.prices["m"] == (1.5, 2.5)


def test_month_to_date_cost(tmp_path):
    now = datetime.now(UTC)
    prefix = now.strftime("%Y%m")
    for run_id, cost in (
        (f"{prefix}01T000000000000-a", 0.5),
        ("19990101T000000000000-b", 1.0),
    ):
        directory = tmp_path / run_id
        directory.mkdir()
        (directory / "run.json").write_text(
            json.dumps({"run_id": run_id, "usage": {"cost_usd": cost}}),
            encoding="utf-8")
    assert month_to_date_cost(tmp_path, now=now) == 0.5
