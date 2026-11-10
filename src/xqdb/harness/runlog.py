import json
from datetime import UTC, datetime
from pathlib import Path


class RunLog:
    def __init__(self, run_dir: Path, run_id: str):
        self.path = Path(run_dir) / run_id
        self.file = self.path / "run.json"

    def write(self, data: dict) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        tmp = self.path / "run.json.tmp"
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.file)


def month_to_date_cost(run_dir: Path,
                       now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    prefix = now.strftime("%Y%m")
    total = 0.0
    for path in Path(run_dir).glob("*/run.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("run_id", "")).startswith(prefix):
            total += float(data.get("usage", {}).get("cost_usd", 0.0))
    return total
