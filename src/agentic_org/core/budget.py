"""Budget object and enforcement.

Every workflow carries a Budget. BudgetTracker.charge() is called before and
after each metered operation; exceeding any limit raises BudgetExceeded so
autonomous loops hit hard stop conditions instead of silently overspending.

Wall-clock is enforced from Spent.started_at (set on first charge).
human_approval_threshold_usd is advisory for UI/CLI (Mode A already has gates).
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .ids import utc_now


class Budget(BaseModel):
    maximum_input_tokens: int = 200_000
    maximum_output_tokens: int = 50_000
    maximum_tool_calls: int = 100
    maximum_iterations: int = 12
    maximum_wall_clock_minutes: int = 60
    maximum_cost_usd: float = 5.0
    expensive_model_call_limit: int = 3
    human_approval_threshold_usd: float = 2.0


class Spent(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    iterations: int = 0
    cost_usd: float = 0.0
    expensive_model_calls: int = 0
    started_at: str | None = None


class BudgetExceeded(Exception):
    def __init__(self, dimension: str, limit: float, attempted: float):
        self.dimension = dimension
        self.limit = limit
        self.attempted = attempted
        super().__init__(f"budget exceeded on {dimension}: {attempted} > {limit}")


def _elapsed_minutes(started_at: str) -> float:
    started = datetime.fromisoformat(started_at)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0.0, (now - started).total_seconds() / 60.0)


class BudgetTracker:
    def __init__(self, budget: Budget, spent: Spent | None = None):
        self.budget = budget
        self.spent = spent or Spent()
        if not self.spent.started_at:
            self.spent.started_at = utc_now()

    def charge(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        tool_calls: int = 0,
        iterations: int = 0,
        cost_usd: float = 0.0,
        expensive_model_calls: int = 0,
    ) -> None:
        if not self.spent.started_at:
            self.spent.started_at = utc_now()
        wall_elapsed = _elapsed_minutes(self.spent.started_at)
        checks = [
            ("maximum_input_tokens", self.spent.input_tokens + input_tokens,
             self.budget.maximum_input_tokens),
            ("maximum_output_tokens", self.spent.output_tokens + output_tokens,
             self.budget.maximum_output_tokens),
            ("maximum_tool_calls", self.spent.tool_calls + tool_calls,
             self.budget.maximum_tool_calls),
            ("maximum_iterations", self.spent.iterations + iterations,
             self.budget.maximum_iterations),
            ("maximum_cost_usd", self.spent.cost_usd + cost_usd,
             self.budget.maximum_cost_usd),
            ("expensive_model_call_limit",
             self.spent.expensive_model_calls + expensive_model_calls,
             self.budget.expensive_model_call_limit),
            ("maximum_wall_clock_minutes", wall_elapsed,
             float(self.budget.maximum_wall_clock_minutes)),
        ]
        for dimension, attempted, limit in checks:
            if attempted > limit:
                raise BudgetExceeded(dimension, limit, attempted)
        self.spent.input_tokens += input_tokens
        self.spent.output_tokens += output_tokens
        self.spent.tool_calls += tool_calls
        self.spent.iterations += iterations
        self.spent.cost_usd += cost_usd
        self.spent.expensive_model_calls += expensive_model_calls

    def requires_human_approval(self) -> bool:
        """Advisory: UI/CLI signal. Not a hard Mode A gate (plan/release gates exist)."""
        return self.spent.cost_usd >= self.budget.human_approval_threshold_usd

    def remaining(self) -> dict[str, float]:
        b, s = self.budget, self.spent
        wall_left = b.maximum_wall_clock_minutes
        if s.started_at:
            wall_left = max(0.0, b.maximum_wall_clock_minutes - _elapsed_minutes(s.started_at))
        return {
            "input_tokens": b.maximum_input_tokens - s.input_tokens,
            "output_tokens": b.maximum_output_tokens - s.output_tokens,
            "tool_calls": b.maximum_tool_calls - s.tool_calls,
            "iterations": b.maximum_iterations - s.iterations,
            "cost_usd": round(b.maximum_cost_usd - s.cost_usd, 6),
            "expensive_model_calls":
                b.expensive_model_call_limit - s.expensive_model_calls,
            "wall_clock_minutes": round(wall_left, 3),
        }
