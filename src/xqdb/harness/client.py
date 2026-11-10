from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)
    id: str = ""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    cost_usd: float = 0.0


class LLMClient(Protocol):
    def complete(self, *, system: str, messages: list[dict],
                 tools: list[dict], max_tokens: int = 4096) -> LLMResponse:
        ...


class AnthropicClient:
    """Thin adapter over the Anthropic SDK.

    Prices are per million tokens and must be supplied by the caller;
    unknown models cost 0.0 rather than guessing.
    """

    def __init__(self, model: str, api_key: str | None = None,
                 prices: dict[str, tuple[float, float]] | None = None):
        self.model = model
        self.api_key = api_key
        self.prices = prices or {}
        self._client = None

    def _cost(self, input_tokens: int, output_tokens: int) -> float:
        input_price, output_price = self.prices.get(self.model, (0.0, 0.0))
        return (input_tokens * input_price
                + output_tokens * output_price) / 1_000_000

    def complete(self, *, system: str, messages: list[dict],
                 tools: list[dict], max_tokens: int = 4096) -> LLMResponse:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.api_key)

        response = self._client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(block.name, block.input, block.id))

        usage = response.usage
        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=self._cost(usage.input_tokens, usage.output_tokens),
        )
