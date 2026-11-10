from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .rules import Finding, check_text, grade

Q_RATE_LIMIT = 0.10


@dataclass(frozen=True)
class ReviewResult:
    edition_id: str
    quality_grade: str
    findings: list[Finding]


@dataclass(frozen=True)
class BatchReport:
    total: int
    q_count: int
    q_rate: float
    blocked: bool
    results: list[ReviewResult]


def review_batch(conn, batch_id: str, corpus_dir: Path) -> BatchReport:
    rows = conn.execute(
        "select id, path from edition where batch_id = ? order by id",
        (batch_id,),
    ).fetchall()

    now = datetime.now(UTC).isoformat()
    results: list[ReviewResult] = []

    signatures = {
        row["id"]: row["simhash"]
        for row in conn.execute(
            "select id, simhash from edition where simhash is not null")
    }
    bands: dict[tuple[int, str], set[str]] = defaultdict(set)
    for edition_key, signature in signatures.items():
        for band in range(4):
            bands[(band, signature[band * 4:(band + 1) * 4])].add(edition_key)

    for row in rows:
        edition_id = row["id"]
        path = corpus_dir / (row["path"] or "")
        text = path.read_text(encoding="utf-8") if path.exists() else ""

        known = None
        signature = signatures.get(edition_id)
        if signature:
            candidates: set[str] = set()
            for band in range(4):
                candidates |= bands[(band, signature[band * 4:(band + 1) * 4])]
            candidates.discard(edition_id)
            known = {key: signatures[key] for key in candidates} or None

        findings = check_text(text, known_hashes=known, signature=signature)
        quality = grade(findings, text)

        conn.execute(
            "delete from review_finding where edition_id = ?", (edition_id,))
        for finding in findings:
            conn.execute(
                "insert into review_finding"
                "(edition_id, kind, severity, evidence, reviewer, decided_at) "
                "values (?, ?, ?, ?, 'rules', ?)",
                (edition_id, finding.kind, finding.severity,
                 finding.evidence, now),
            )
        conn.execute(
            "update edition set quality_grade = ?, review_status = 'reviewed', "
            "provenance_class = coalesce(provenance_class, 'unknown') "
            "where id = ?",
            (quality, edition_id),
        )
        results.append(ReviewResult(edition_id, quality, findings))

    conn.commit()

    total = len(results)
    q_count = sum(1 for result in results if result.quality_grade == "Q")
    q_rate = q_count / total if total else 0.0
    blocked = total > 0 and q_rate >= Q_RATE_LIMIT

    return BatchReport(
        total=total,
        q_count=q_count,
        q_rate=q_rate,
        blocked=blocked,
        results=results,
    )
