from dataclasses import dataclass
from pathlib import Path

from ..harness.runner import Runner
from ..tools.registry import TOOL_SPECS
from .chunk import iter_chunks
from .persist import persist_annotation, record_state
from .schema import AnnotationInvalid, parse_annotation, validate_annotation

DEFAULT_SCHEMA = Path("schemas/agents/annotator.schema.json")


@dataclass
class BatchResult:
    processed: int = 0
    ok: int = 0
    failed: int = 0
    rejected: int = 0
    stopped_reason: str | None = None


def _task(chunk) -> str:
    passage_ids = ", ".join(chunk.passage_ids)
    return (
        f"章节 {chunk.section_id}。\n"
        f"只允许为这些 passage_id 输出标注：{passage_ids}\n"
        f"正文：\n{chunk.text}\n"
        "只输出 JSON，不要解释。"
    )


def annotate_batch(conn, role, client, budget, runs_dir, ctx, *,
                   limit: int = 20, max_chars: int = 4000,
                   dry_run: bool = False, force: bool = False,
                   max_retries: int = 1) -> BatchResult:
    schema_path = Path(role.output_schema)
    if not schema_path.exists():
        schema_path = DEFAULT_SCHEMA

    result = BatchResult()
    for chunk in iter_chunks(
            conn, max_chars=max_chars, only_unannotated=True, force=force):
        if result.processed >= limit:
            break
        result.processed += 1

        if dry_run:
            print(f"dry-run {chunk.chunk_id} "
                  f"passages={len(chunk.passage_ids)} chars={chunk.char_count}")
            continue

        task = _task(chunk)
        attempts = 0
        last_error = None
        success = False

        while attempts <= max_retries:
            attempts += 1
            run = Runner(role, TOOL_SPECS, client, budget, runs_dir,
                         ctx=ctx).run(task)
            if run.status == "budget_exceeded":
                result.stopped_reason = "budget_exceeded"
                return result
            if run.status != "ok":
                last_error = run.output
                continue

            try:
                payload = parse_annotation(run.output)
                validate_annotation(payload, schema_path)
                counts = persist_annotation(
                    conn, chunk, payload, model=role.name)
                record_state(conn, chunk.chunk_id, chunk.section_id, "ok",
                             attempts=attempts, model=role.name)
                result.ok += 1
                result.rejected += counts.get("rejected", 0)
                success = True
                break
            except (AnnotationInvalid, Exception) as exc:  # noqa: BLE001
                last_error = str(exc)

        if not success:
            result.failed += 1
            record_state(conn, chunk.chunk_id, chunk.section_id, "error",
                         attempts=attempts, error=last_error, model=role.name)

    return result
