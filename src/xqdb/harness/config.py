from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AgentConfig:
    model: str
    monthly_budget_usd: float
    runs_dir: Path
    agents_dir: Path
    schemas_dir: Path
    prices: dict[str, tuple[float, float]]


def load_agent_config(root: Path | None = None) -> AgentConfig:
    root = Path(root if root is not None else Path.cwd()).resolve()
    path = root / "config" / "config.yaml"
    raw = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    agent = raw.get("agent") or {}

    def resolve(key: str, default: str) -> Path:
        value = Path(agent.get(key, default))
        return value if value.is_absolute() else root / value

    return AgentConfig(
        model=agent.get("model", "claude-sonnet-5-5"),
        monthly_budget_usd=float(agent.get("monthly_budget_usd", 20.0)),
        runs_dir=resolve("runs_dir", "data/runs"),
        agents_dir=resolve("agents_dir", "agents"),
        schemas_dir=resolve("schemas_dir", "schemas/agents"),
        prices={
            name: (float(values[0]), float(values[1]))
            for name, values in (agent.get("prices") or {}).items()
        },
    )
