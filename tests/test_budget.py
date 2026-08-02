import pytest

from agentic_org.core.budget import Budget, BudgetExceeded, BudgetTracker


def test_charge_accumulates():
    tracker = BudgetTracker(Budget(maximum_cost_usd=1.0))
    tracker.charge(cost_usd=0.4, input_tokens=100)
    tracker.charge(cost_usd=0.4)
    assert abs(tracker.spent.cost_usd - 0.8) < 1e-9
    assert tracker.remaining()["cost_usd"] == pytest.approx(0.2)


def test_exceeding_cost_raises():
    tracker = BudgetTracker(Budget(maximum_cost_usd=1.0))
    tracker.charge(cost_usd=0.9)
    with pytest.raises(BudgetExceeded) as exc:
        tracker.charge(cost_usd=0.2)
    assert exc.value.dimension == "maximum_cost_usd"
    # Failed charge must not be applied.
    assert tracker.spent.cost_usd == pytest.approx(0.9)


def test_iteration_limit():
    tracker = BudgetTracker(Budget(maximum_iterations=2))
    tracker.charge(iterations=1)
    tracker.charge(iterations=1)
    with pytest.raises(BudgetExceeded):
        tracker.charge(iterations=1)


def test_human_approval_threshold():
    tracker = BudgetTracker(Budget(maximum_cost_usd=10.0,
                                   human_approval_threshold_usd=2.0))
    tracker.charge(cost_usd=1.9)
    assert not tracker.requires_human_approval()
    tracker.charge(cost_usd=0.2)
    assert tracker.requires_human_approval()
