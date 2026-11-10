from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..annotate.schema import parse_annotation, validate_annotation
from ..harness.runner import Runner
from ..tools.registry import TOOL_SPECS

SCHEMA = Path("schemas/agents/reviewer.schema.json")
PROVENANCE_CLASSES = {
    "contemporary", "retrospective", "pseudepigraphic", "unknown"}


@dataclass
class LLMReviewReport:
    checked: int = 0
    updated: int = 0
    findings_written: int = 0
    stopped_reason: str | None = None


def _task(row, snippet: str) -> str:
    return (
        f"审核 edition {row['id']}（《{row['title']}》，约 {row['char_count']} 字）。\n"
        f"当前质量等级：{row['quality_grade']}；性质：{row['provenance_class']}。\n"
        f"片段：\n{snippet}\n"
        '只输出 JSON：{"findings": [{"edition_id", "kind", "severity", '
        '"evidence", "quality_grade", "provenance_class"}]}'
    )


def review_llm_batch(conn, role, client_factory, budget, runs_dir, ctx, *,
                     limit: int = 10, apply: bool = True) -> LLMReviewReport:
    rows = conn.execute(
        """
        select e.id, e.path, e.char_count, e.work_id, e.quality_grade,
               e.provenance_class, w.title
        from edition e
        join work w on w.id = e.work_id
        order by (e.review_status = 'reviewed') desc, e.id
        limit ?
        """,
        (limit,),
    ).fetchall()

    report = LLMReviewReport()
    for row in rows:
        report.checked += 1

        snippet = ""
        if row["path"]:
            path = ctx.cfg.corpus_dir / row["path"]
            if path.exists():
                snippet = path.read_text(encoding="utf-8")[:2000]

        runner = Runner(role, TOOL_SPECS, client_factory(), budget,
                        runs_dir, ctx=ctx)
        result = runner.run(_task(row, snippet))
        if result.status == "budget_exceeded":
            report.stopped_reason = "budget_exceeded"
            break
        if result.status != "ok":
            continue

        try:
            payload = parse_annotation(result.output)
            validate_annotation(payload, SCHEMA)
        except Exception:  # noqa: BLE001 - invalid output writes nothing
            continue  # noqa: S112

        findings = [
            item for item in payload.get("findings", [])
            if item.get("edition_id") == row["id"]
        ]
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "delete from review_finding where edition_id = ? and reviewer = 'llm'",
            (row["id"],),
        )
        for item in findings:
            conn.execute(
                "insert into review_finding"
                "(edition_id, kind, severity, evidence, reviewer, decided_at) "
                "values (?, ?, ?, ?, 'llm', ?)",
                (row["id"], item["kind"], item.get("severity", "warn"),
                 item.get("evidence"), now),
            )
        report.findings_written += len(findings)

        if apply:
            changed = False
            quality = next(
                (item["quality_grade"] for item in findings
                 if item.get("quality_grade") in ("A", "B", "C")), None)
            if quality and row["quality_grade"] != "Q" \
                    and quality != row["quality_grade"]:
                conn.execute(
                    "update edition set quality_grade = ? where id = ?",
                    (quality, row["id"]))
                changed = True

            provenance = next(
                (item["provenance_class"] for item in findings
                 if item.get("provenance_class") in PROVENANCE_CLASSES), None)
            if provenance and provenance != row["provenance_class"]:
                conn.execute(
                    "update edition set provenance_class = ? where id = ?",
                    (provenance, row["id"]))
                changed = True
            if changed:
                report.updated += 1

        conn.commit()

    return report
