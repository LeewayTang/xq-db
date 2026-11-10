import json
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
