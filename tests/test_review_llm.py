from pathlib import Path

from xqdb.harness.budget import Budget
from xqdb.harness.client import LLMResponse
from xqdb.harness.roles import AgentRole
from xqdb.review.llm import review_llm_batch


class Factory:
    def __init__(self, text):
        self.text = text
        self.created = 0

    def __call__(self):
        self.created += 1
        text = self.text

        class Client:
            def complete(self, messages, *, tools, system=""):
                return LLMResponse(text, [], 10, 10, 0.0)

        return Client()


def _role():
    return AgentRole("reviewer", "t", ("get_passage",), Path("none"),
                     1000, 5, 1.0, True, "p")


def test_llm_review_updates_grade_and_provenance(ctx):
    payload = ('{"findings": [{"edition_id": "e:z", "kind": "late_composition",'
               ' "severity": "warn", "evidence": "x", "quality_grade": "B",'
               ' "provenance_class": "retrospective"}]}')
    factory = Factory(payload)
    report = review_llm_batch(ctx.conn, _role(), factory, Budget(1000, 10, 1.0),
                              ctx.cfg.data_dir / "runs", ctx, limit=1)
    assert report.updated == 1 and report.findings_written == 1
    row = ctx.conn.execute(
        "select quality_grade, provenance_class from edition where id='e:z'").fetchone()
    assert row["quality_grade"] == "B"
    assert row["provenance_class"] == "retrospective"
    assert factory.created == 1


def test_rule_q_is_protected(ctx):
    ctx.conn.execute("update edition set quality_grade='Q' where id='e:z'")
    ctx.conn.commit()
    payload = ('{"findings": [{"edition_id": "e:z", "kind": "late_composition",'
               ' "severity": "warn", "evidence": "x", "quality_grade": "A"}]}')
    review_llm_batch(ctx.conn, _role(), Factory(payload), Budget(1000, 10, 1.0),
                     ctx.cfg.data_dir / "runs", ctx, limit=1)
    assert ctx.conn.execute(
        "select quality_grade from edition where id='e:z'").fetchone()[0] == "Q"


def test_invalid_json_records_no_findings(ctx):
    report = review_llm_batch(ctx.conn, _role(), Factory("not json"),
                              Budget(1000, 10, 1.0),
                              ctx.cfg.data_dir / "runs", ctx, limit=1)
    assert report.findings_written == 0
    assert ctx.conn.execute(
        "select count(*) from review_finding").fetchone()[0] == 0
