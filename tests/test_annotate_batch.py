from pathlib import Path

from xqdb.annotate.batch import annotate_batch
from xqdb.harness.budget import Budget
from xqdb.harness.client import LLMResponse
from xqdb.harness.roles import AgentRole

FIXTURE = Path("tests/fixtures/annotations/zuozhuan.json")


class FakeClient:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = 0

    def complete(self, messages, *, tools, system=""):
        self.calls += 1
        return LLMResponse(self.texts.pop(0), [], 10, 10, 0.0)


def _role():
    return AgentRole("annotator", "t", ("get_passage",), Path("none"),
                     1000, 10, 1.0, True, "p")


def test_batch_annotates_and_records_state(ctx):
    payload = FIXTURE.read_text("utf-8")
    result = annotate_batch(
        ctx.conn, _role(), FakeClient([payload]), Budget(1000, 10, 1.0),
        ctx.cfg.data_dir / "runs", ctx)
    assert result.processed == 1 and result.ok == 1
    assert ctx.conn.execute("select count(*) from mention").fetchone()[0] > 0
    assert ctx.conn.execute("select status from annotation_state").fetchone()[0] == "ok"


def test_batch_retries_bad_json_then_records_error(ctx):
    client = FakeClient(["not json", "still not json"])
    result = annotate_batch(
        ctx.conn, _role(), client, Budget(1000, 10, 1.0),
        ctx.cfg.data_dir / "runs", ctx, max_retries=1)
    assert result.failed == 1
    assert ctx.conn.execute("select status from annotation_state").fetchone()[0] == "error"


def test_dry_run_makes_no_client_call(ctx):
    client = FakeClient([])
    result = annotate_batch(
        ctx.conn, _role(), client, Budget(1000, 10, 1.0),
        ctx.cfg.data_dir / "runs", ctx, dry_run=True)
    assert result.processed == 1 and client.calls == 0


def test_batch_resumes_past_ok_chunks(ctx):
    payload = FIXTURE.read_text("utf-8")
    annotate_batch(ctx.conn, _role(), FakeClient([payload]),
                   Budget(1000, 10, 1.0), ctx.cfg.data_dir / "runs", ctx)
    result = annotate_batch(ctx.conn, _role(), FakeClient([]),
                            Budget(1000, 10, 1.0), ctx.cfg.data_dir / "runs", ctx)
    assert result.processed == 0


def test_budget_stop_is_resumable(ctx):
    payload = FIXTURE.read_text("utf-8")
    result = annotate_batch(
        ctx.conn, _role(), FakeClient([payload]), Budget(1, 10, 1.0),
        ctx.cfg.data_dir / "runs", ctx)
    assert result.stopped_reason == "budget_exceeded"
    assert ctx.conn.execute(
        "select count(*) from annotation_state").fetchone()[0] == 0
