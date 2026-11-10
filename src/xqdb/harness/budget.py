from dataclasses import dataclass


class BudgetExceeded(Exception):
    def __init__(self, limit: str, used):
        self.limit = limit
        self.used = used
        super().__init__(f"budget exceeded: {limit}={used}")


@dataclass
class Budget:
    max_tokens: int
    max_tool_calls: int
    max_cost_usd: float
    tokens: int = 0
    tool_calls: int = 0
    cost_usd: float = 0.0

    def _check(self) -> None:
        if self.tokens > self.max_tokens:
            raise BudgetExceeded("tokens", self.tokens)
        if self.tool_calls > self.max_tool_calls:
            raise BudgetExceeded("tool_calls", self.tool_calls)
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceeded("cost_usd", self.cost_usd)

    def charge_tokens(self, count: int) -> None:
        self.tokens += count
        self._check()

    def charge_tool(self) -> None:
        self.tool_calls += 1
        self._check()

    def charge_cost(self, amount: float) -> None:
        self.cost_usd += amount
        self._check()
