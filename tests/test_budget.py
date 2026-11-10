import pytest

from xqdb.harness.budget import Budget, BudgetExceeded


def test_charges_accumulate():
    budget = Budget(max_tokens=100, max_tool_calls=2, max_cost_usd=1.0)
    budget.charge_tokens(60)
    budget.charge_tool()
    budget.charge_cost(0.4)
    assert budget.tokens == 60 and budget.tool_calls == 1
    assert budget.cost_usd == pytest.approx(0.4)


def test_limit_is_inclusive():
    budget = Budget(max_tokens=10, max_tool_calls=1, max_cost_usd=0.01)
    budget.charge_tokens(10)
    budget.charge_tool()


def test_exceeding_any_limit_raises():
    budget = Budget(max_tokens=1, max_tool_calls=1, max_cost_usd=0.01)
    with pytest.raises(BudgetExceeded):
        budget.charge_tokens(2)

    other = Budget(max_tokens=10, max_tool_calls=1, max_cost_usd=0.01)
    other.charge_tool()
    with pytest.raises(BudgetExceeded):
        other.charge_tool()
