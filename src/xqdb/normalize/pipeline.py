import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from .encoding import decode_bytes
from .ids import edition_id, slugify_title, work_id
from .parse import parse_daizhige_text
from .simhash import simhash64


@dataclass(frozen=True)
class NormalizeResult:
    edition_id: str
    work_id: str
    title: str
    path: Path
    char_count: int
    sha256: str
    simhash: str
    sections: list


def _render_body(sections) -> str:
    blocks: list[str] = []
    for section in sections:
        blocks.append(f"## {section.title}")
        if section.lines:
            blocks.append("\n".join(section.lines))
    return "\n\n".join(blocks) + "\n"


def normalize_file(
    raw: Path,
    rel_path: str,
    source: str,
    corpus_dir: Path,
) -> NormalizeResult:
    data = raw.read_bytes()
    decoded = decode_bytes(data)
    title = Path(rel_path).stem
    parsed = parse_daizhige_text(decoded.text, title)

    wid = work_id(title)
    eid = edition_id(wid, source)
    sha = hashlib.sha256(data).hexdigest()
    body = _render_body(parsed.sections)
    char_count = sum(1 for ch in body if not ch.isspace())
    digest = simhash64(body)

    out_path = corpus_dir / source / f"{slugify_title(title)}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    meta = {
        "id": eid,
        "work_id": wid,
        "title": title,
        "source": source,
        "source_path": rel_path,
        "encoding": decoded.encoding,
        "had_bom": decoded.had_bom,
        "char_count": char_count,
        "sha256": sha,
        "simhash": digest,
        "sections": len(parsed.sections),
        "front_matter": parsed.front_matter,
    }
    header = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    out_path.write_text(f"---\n{header}---\n\n{body}", encoding="utf-8")

    return NormalizeResult(
        edition_id=eid,
        work_id=wid,
        title=title,
        path=out_path,
        char_count=char_count,
        sha256=sha,
        simhash=digest,
        sections=parsed.sections,
    )
