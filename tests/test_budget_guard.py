from __future__ import annotations

import pytest

from app.budget.apify_budget import ApifyBudgetGuard, BudgetExceededError, _extract_monthly_usage_usd


def test_extract_monthly_usage_usd_from_total_field():
    payload = {"data": {"totalUsageCreditsUsdAfterVolumeDiscount": 4.25}}
    assert _extract_monthly_usage_usd(payload) == 4.25


def test_budget_guard_blocks_when_safe_budget_is_exceeded(monkeypatch):
    guard = ApifyBudgetGuard(
        token="fake",
        monthly_budget_usd=5.0,
        safety_buffer_usd=0.10,
        enabled=True,
        enable_platform_hard_limit=False,
    )
    monkeypatch.setattr(guard, "get_monthly_usage_usd", lambda: 4.95)

    with pytest.raises(BudgetExceededError):
        guard.assert_can_run("test-source", estimated_cost_usd=0.10)
