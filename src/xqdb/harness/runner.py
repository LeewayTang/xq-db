import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .budget import Budget, BudgetExceeded
from .runlog import RunLog

MAX_TURNS = 8
CITATION_RULE = "每条结论必须附 passage_id；没有出处的判断必须标注为推断。"


@dataclass(frozen=True)
class RunResult:
    status: str
    output: str
    citations: list[str]
    tool_calls: list[dict]
    usage: dict
    log_path: Path


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
                "input_schema": {"type": "object"},
            }
            for name in self.role.tools
        ]

    def _log(self, run_id: str, status: str, task: str,
             messages: list[dict], tool_calls: list[dict],
             citations: list[str]) -> Path:
        log = RunLog(self.run_dir, run_id)
        log.write({
            "run_id": run_id,
            "role": self.role.name,
            "task": task,
            "status": status,
            "messages": messages,
            "tool_calls": tool_calls,
            "citations": citations,
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

        log_path = self._log(
            run_id, status, task, messages, called, citations)
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
        )
