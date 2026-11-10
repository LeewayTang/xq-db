import json
from pathlib import Path

import jsonschema


class AnnotationInvalid(ValueError):
    pass


def validate_annotation(payload: dict, schema_path: Path) -> None:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: error.path)
    if errors:
        messages = [
            f"{'/'.join(str(part) for part in error.path)}: {error.message}"
            for error in errors
        ]
        raise AnnotationInvalid("; ".join(messages))


def parse_annotation(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnnotationInvalid(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AnnotationInvalid("annotation must be a JSON object")
    return payload
