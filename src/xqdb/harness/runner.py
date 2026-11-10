import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..tools.registry import tool_schema
from .budget import Budget, BudgetExceeded
from .runlog import RunLog

MAX_TURNS = 8
CITATION_RULE = "每条结论必须附 passage_id；没有出处的判断必须标注为推断。"
CITATION_PATTERN = re.compile(r"(?<![A-Za-z0-9_:-])(p:[A-Za-z0-9:_-]+)")


@dataclass(frozen=True)
class RunResult:
    status: str
    output: str
    citations: list[str]
    tool_calls: list[dict]
    usage: dict
    log_path: Path
    invalid_citations: list[str] = field(default_factory=list)


def _collect_citations(value, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "passage_id" and isinstance(item, str):
                if item not in out:
                    out.append(item)
            else:
                _collect_citations(item, out)
    elif isinstance(value, list):
        for item in value:
            _collect_citations(item, out)


class Runner:
    def __init__(self, role, tool_specs, client, budget: Budget,
                 run_dir: Path, *, ctx=None, max_turns: int = MAX_TURNS):
        self.role = role
        self.tool_specs = tool_specs
        self.client = client
        self.budget = budget
        self.run_dir = Path(run_dir)
        self.ctx = ctx
        self.max_turns = max_turns

    def _tool_defs(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": self.tool_specs[name].description,
                "input_schema": tool_schema(self.tool_specs[name].func),
            }
            for name in self.role.tools
        ]

    def _log(self, run_id: str, status: str, task: str,
             messages: list[dict], tool_calls: list[dict],
             citations: list[str],
             invalid_citations: list[str]) -> Path:
        log = RunLog(self.run_dir, run_id)
        log.write({
            "run_id": run_id,
            "role": self.role.name,
            "task": task,
            "status": status,
            "messages": messages,
            "tool_calls": tool_calls,
            "citations": citations,
            "invalid_citations": invalid_citations,
            "usage": {
                "tokens": self.budget.tokens,
                "tool_calls": self.budget.tool_calls,
                "cost_usd": self.budget.cost_usd,
            },
        })
        return log.path

    def run(self, task: str) -> RunResult:
        run_id = (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
            + "-" + secrets.token_hex(3))
        messages: list[dict] = [{"role": "user", "content": task}]
        system = f"{self.role.prompt}\n\n{CITATION_RULE}"
        citations: list[str] = []
        called: list[dict] = []
        status = "running"
        output = ""

        try:
            for _ in range(self.max_turns):
                response = self.client.complete(
                    messages, tools=self._tool_defs(), system=system)
                self.budget.charge_tokens(
                    response.input_tokens + response.output_tokens)
                self.budget.charge_cost(response.cost_usd)

                if not response.tool_calls:
                    output = response.text
                    status = "ok"
                    break

                assistant_content: list[dict] = []
                if response.text:
                    assistant_content.append(
                        {"type": "text", "text": response.text})
                for call in response.tool_calls:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    })
                messages.append(
                    {"role": "assistant", "content": assistant_content})

                tool_results: list[dict] = []
                for call in response.tool_calls:
                    if call.name not in self.role.tools:
                        status = "error"
                        output = f"tool not allowed: {call.name}"
                        break
                    self.budget.charge_tool()
                    spec = self.tool_specs[call.name]
                    result = spec.func(self.ctx, **call.arguments)
                    called.append({
                        "name": call.name,
                        "arguments": call.arguments,
                        "result": result,
                    })
                    _collect_citations(result, citations)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                if status == "error":
                    break
                messages.append({"role": "user", "content": tool_results})
            else:
                status = "error"
                output = "max turns exceeded"
        except BudgetExceeded as exc:
            status = "budget_exceeded"
            output = f"budget exceeded: {exc.limit}"
        except Exception as exc:  # noqa: BLE001 - every failure must be logged
            status = "error"
            output = f"{type(exc).__name__}: {exc}"

        invalid: list[str] = []
        for match in CITATION_PATTERN.findall(output):
            if match not in citations:
                citations.append(match)
        if self.ctx is not None:
            for passage_id in citations:
                exists = self.ctx.conn.execute(
                    "select 1 from passage where id = ?", (passage_id,)
                ).fetchone()
                if exists is None:
                    invalid.append(passage_id)
            if invalid and status == "ok":
                status = "citation_error"

        log_path = self._log(
            run_id, status, task, messages, called, citations, invalid)
        return RunResult(
            status=status,
            output=output,
            citations=citations,
            tool_calls=called,
            usage={
                "tokens": self.budget.tokens,
                "tool_calls": self.budget.tool_calls,
                "cost_usd": self.budget.cost_usd,
            },
            log_path=log_path,
            invalid_citations=invalid,
        )
