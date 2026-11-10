import json
from pathlib import Path

from xqdb.harness.budget import Budget
from xqdb.harness.client import LLMResponse, ToolCall
from xqdb.harness.roles import AgentRole
from xqdb.harness.runner import Runner
from xqdb.tools.registry import TOOL_SPECS


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, messages, *, tools, system=""):
        self.calls += 1
        return self.responses.pop(0)


def _role(tools=("search_keyword", "get_passage")):
    return AgentRole(
        name="researcher", description="t", tools=tools,
        output_schema=Path("none"), max_tokens=1000,
        max_tool_calls=5, max_cost_usd=1.0,
        fresh_context=True, prompt="p")


def test_runner_executes_tool_then_answers(ctx, tmp_path):
    client = FakeClient([
        LLMResponse("", [ToolCall("search_keyword",
                                  {"query": "郑伯克段"}, "t1")], 10, 5, 0.01),
        LLMResponse("结论 [p:z:1:001]", [], 20, 10, 0.02),
    ])
    result = Runner(_role(), TOOL_SPECS, client, Budget(1000, 5, 1.0),
                    tmp_path / "runs", ctx=ctx).run("查")
    assert result.status == "ok"
    assert result.citations == ["p:z:1:001"]
    log = json.loads((result.log_path / "run.json").read_text("utf-8"))
    assert log["status"] == "ok"
    assert log["tool_calls"][0]["name"] == "search_keyword"


def test_runner_rejects_unauthorized_tool(ctx, tmp_path):
    client = FakeClient([
        LLMResponse("", [ToolCall("get_work", {"work_id": "w:z"}, "t1")],
                    1, 1, 0.0),
        LLMResponse("done", [], 1, 1, 0.0),
    ])
    result = Runner(_role(("search_keyword",)), TOOL_SPECS, client,
                    Budget(1000, 5, 1.0), tmp_path / "runs", ctx=ctx).run("x")
    assert result.status == "error"
    assert "not allowed" in result.output


def test_runner_stops_on_budget(ctx, tmp_path):
    client = FakeClient([
        LLMResponse("", [ToolCall("search_keyword", {"query": "a"}, "t1")],
                    1, 1, 0.0),
        LLMResponse("", [ToolCall("search_keyword", {"query": "b"}, "t2")],
                    1, 1, 0.0),
    ])
    result = Runner(_role(), TOOL_SPECS, client, Budget(1000, 1, 1.0),
                    tmp_path / "runs", ctx=ctx).run("x")
    assert result.status == "budget_exceeded"
    assert (result.log_path / "run.json").exists()


def test_answer_citations_exist_in_corpus(ctx, tmp_path):
    from xqdb.tools.corpus import get_passage

    client = FakeClient([
        LLMResponse("", [ToolCall("search_keyword",
                                  {"query": "郑伯克段"}, "t1")], 5, 5, 0.0),
        LLMResponse("", [ToolCall("search_keyword",
                                  {"query": "郑伯克段"}, "t2")], 5, 5, 0.0),
        LLMResponse("见 [p:z:1:001]", [], 5, 5, 0.0),
    ])
    result = Runner(_role(), TOOL_SPECS, client, Budget(1000, 5, 1.0),
                    tmp_path / "runs", ctx=ctx).run("查")
    assert result.citations == ["p:z:1:001"]
    for passage_id in result.citations:
        assert get_passage(ctx, passage_id).get("error") is None


def test_runner_flags_unknown_citations(ctx, tmp_path):
    client = FakeClient([
        LLMResponse("见 [p:does-not-exist]", [], 5, 5, 0.0),
    ])
    result = Runner(_role(), TOOL_SPECS, client, Budget(1000, 5, 1.0),
                    tmp_path / "runs", ctx=ctx).run("查")
    assert result.status == "citation_error"
    assert result.invalid_citations == ["p:does-not-exist"]


def test_runner_advertises_tool_parameters(ctx, tmp_path):
    runner = Runner(_role(), TOOL_SPECS, FakeClient([]), Budget(10, 1, 1.0),
                    tmp_path / "runs", ctx=ctx)
    defs = {item["name"]: item for item in runner._tool_defs()}
    schema = defs["search_keyword"]["input_schema"]
    assert schema["properties"]["query"]["type"] == "string"
    assert "query" in schema["required"]


def test_runner_writes_log_on_tool_error(ctx, tmp_path):
    client = FakeClient([
        LLMResponse("", [ToolCall("search_keyword", {}, "t1")], 1, 1, 0.0),
    ])
    result = Runner(_role(), TOOL_SPECS, client, Budget(100, 5, 1.0),
                    tmp_path / "runs", ctx=ctx).run("查")
    assert result.status == "error"
    assert (result.log_path / "run.json").exists()
