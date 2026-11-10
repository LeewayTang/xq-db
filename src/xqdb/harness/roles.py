from dataclasses import dataclass
from pathlib import Path

import yaml

from ..tools.registry import TOOL_SPECS

BUDGET_KEYS = ("max_tokens", "max_tool_calls", "max_cost_usd")


@dataclass(frozen=True)
class AgentRole:
    name: str
    description: str
    tools: tuple[str, ...]
    output_schema: str
    max_tokens: int
    max_tool_calls: int
    max_cost_usd: float
    fresh_context: bool
    prompt: str
    allow_admin: bool = False


def _parse_role(path: Path, schemas_dir: Path) -> AgentRole:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing frontmatter")
    _, frontmatter, body = text.split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}

    name = meta.get("role")
    if name != path.stem:
        raise ValueError(f"{path}: role {name!r} does not match filename")

    tools = tuple(meta.get("tools") or ())
    allow_admin = bool(meta.get("allow_admin", False))
    for tool in tools:
        spec = TOOL_SPECS.get(tool)
        if spec is None:
            raise ValueError(f"{path}: unknown tool {tool!r}")
        if spec.admin and not allow_admin:
            raise ValueError(
                f"{path}: admin tool {tool!r} requires allow_admin: true")

    budget = meta.get("budget") or {}
    for key in BUDGET_KEYS:
        value = budget.get(key)
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"{path}: budget.{key} must be positive")

    output_schema = meta.get("output_schema")
    if not output_schema or not (schemas_dir / output_schema).exists():
        raise ValueError(f"{path}: missing output schema {output_schema!r}")

    return AgentRole(
        name=name,
        description=meta.get("description", ""),
        tools=tools,
        output_schema=str(schemas_dir / output_schema),
        max_tokens=budget["max_tokens"],
        max_tool_calls=budget["max_tool_calls"],
        max_cost_usd=float(budget["max_cost_usd"]),
        fresh_context=bool(meta.get("fresh_context", True)),
        prompt=body.strip(),
        allow_admin=allow_admin,
    )


def load_roles(agents_dir: Path, *,
               schemas_dir: Path | None = None) -> dict[str, AgentRole]:
    agents_dir = Path(agents_dir)
    if schemas_dir is None:
        schemas_dir = agents_dir.parent / "schemas" / "agents"
    schemas_dir = Path(schemas_dir)

    roles = {}
    for path in sorted(agents_dir.glob("*.md")):
        role = _parse_role(path, schemas_dir)
        roles[role.name] = role
    return roles


def load_role(agents_dir: Path, name: str) -> AgentRole:
    return load_roles(agents_dir)[name]
