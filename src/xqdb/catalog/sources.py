from dataclasses import dataclass
from pathlib import Path

import yaml

TRUST_LEVELS = {"primary", "secondary", "tertiary", "unknown"}
REQUIRED = ("name", "url", "license", "trust")


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    url: str
    license: str
    trust: str
    notes: str = ""


def load_sources(path: Path) -> dict[str, Source]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result: dict[str, Source] = {}
    for source_id, item in data.items():
        if not isinstance(item, dict):
            raise ValueError(f"source {source_id!r} must be a mapping")  # noqa: TRY004
        missing = [key for key in REQUIRED if key not in item]
        if missing:
            raise ValueError(f"source {source_id!r} missing {missing}")
        if item["trust"] not in TRUST_LEVELS:
            raise ValueError(
                f"source {source_id!r} has invalid trust {item['trust']!r}")
        result[source_id] = Source(
            id=source_id,
            name=item["name"],
            url=item["url"],
            license=item["license"],
            trust=item["trust"],
            notes=item.get("notes", ""),
        )
    return result
