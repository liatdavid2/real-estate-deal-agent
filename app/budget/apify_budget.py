from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BudgetGuardError(RuntimeError):
    pass


class BudgetExceededError(BudgetGuardError):
    pass


@dataclass(frozen=True)
class BudgetStatus:
    enabled: bool
    budget_usd: float
    current_usage_usd: float | None
    remaining_usd: float | None
    safety_buffer_usd: float
    hard_limit_enabled: bool
    note: str = ""


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_monthly_usage_usd(payload: dict[str, Any]) -> float | None:
    """Extract monthly USD usage from Apify responses.

    Apify may add or rename fields over time. Prefer documented/current total fields,
    then fall back to recursively searching for USD usage-like fields.
    """
    data = payload.get("data", payload)
    preferred_paths = [
        ("totalUsageCreditsUsdAfterVolumeDiscount",),
        ("totalUsageCreditsUsdBeforeVolumeDiscount",),
        ("monthlyUsageUsd",),
        ("currentMonthlyUsageUsd",),
        ("usage", "monthlyUsageUsd"),
        ("currentUsage", "monthlyUsageUsd"),
        ("usage", "totalUsageUsd"),
        ("currentUsage", "totalUsageUsd"),
    ]
    for path in preferred_paths:
        cur: Any = data
        for part in path:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                cur = None
                break
        val = _safe_float(cur)
        if val is not None:
            return val

    candidates: list[float] = []

    def walk(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_path = f"{path}.{key}" if path else str(key)
                lower_key = str(key).lower()
                value_float = _safe_float(value)
                if value_float is not None and "usd" in lower_key and any(
                    token in lower_key for token in ["total", "usage", "charge", "cost", "credit"]
                ):
                    candidates.append(value_float)
                walk(value, key_path)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, path)

    walk(data)
    if candidates:
        return max(candidates)
    return None


class ApifyBudgetGuard:
    def __init__(
        self,
        token: str | None = None,
        monthly_budget_usd: float | None = None,
        safety_buffer_usd: float | None = None,
        enabled: bool | None = None,
        enable_platform_hard_limit: bool | None = None,
        fail_closed: bool | None = None,
    ):
        self.token = token or os.getenv("APIFY_TOKEN")
        self.enabled = _env_bool("APIFY_BUDGET_GUARD_ENABLED", True) if enabled is None else enabled
        self.monthly_budget_usd = monthly_budget_usd if monthly_budget_usd is not None else float(os.getenv("APIFY_MONTHLY_BUDGET_USD", "5.0"))
        self.safety_buffer_usd = safety_buffer_usd if safety_buffer_usd is not None else float(os.getenv("APIFY_BUDGET_SAFETY_BUFFER_USD", "0.10"))
        self.enable_platform_hard_limit = _env_bool("APIFY_SET_PLATFORM_HARD_LIMIT", True) if enable_platform_hard_limit is None else enable_platform_hard_limit
        self.fail_closed = _env_bool("APIFY_BUDGET_FAIL_CLOSED", True) if fail_closed is None else fail_closed
        self._hard_limit_attempted = False

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.token:
            raise BudgetGuardError("APIFY_TOKEN is required for Apify budget checks.")
        url = f"https://api.apify.com/v2{path}"
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url, data=payload, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise BudgetGuardError(f"Apify budget API failed: HTTP {exc.code}: {details}") from exc
        except URLError as exc:
            raise BudgetGuardError(f"Apify budget API failed: {exc.reason}") from exc

    def get_monthly_usage_usd(self) -> float | None:
        payload = self._request("GET", "/users/me/usage/monthly")
        return _extract_monthly_usage_usd(payload)

    def get_limits(self) -> dict[str, Any]:
        return self._request("GET", "/users/me/limits")

    def set_platform_hard_limit(self) -> str:
        if not self.enabled or not self.enable_platform_hard_limit:
            return "Platform hard limit is disabled by config."
        if self._hard_limit_attempted:
            return "Platform hard limit was already checked in this run."
        self._hard_limit_attempted = True
        self._request("PUT", "/users/me/limits", {"maxMonthlyUsageUsd": self.monthly_budget_usd})
        return f"Apify platform hard limit set to ${self.monthly_budget_usd:.2f}."

    def status(self) -> BudgetStatus:
        if not self.enabled:
            return BudgetStatus(False, self.monthly_budget_usd, None, None, self.safety_buffer_usd, self.enable_platform_hard_limit, "Budget guard disabled.")
        usage = self.get_monthly_usage_usd()
        if usage is None:
            note = "Could not read Apify monthly usage from API response."
            if self.fail_closed:
                raise BudgetGuardError(note)
            return BudgetStatus(True, self.monthly_budget_usd, None, None, self.safety_buffer_usd, self.enable_platform_hard_limit, note)
        remaining = self.monthly_budget_usd - usage
        return BudgetStatus(True, self.monthly_budget_usd, usage, remaining, self.safety_buffer_usd, self.enable_platform_hard_limit)

    def assert_can_run(self, label: str, estimated_cost_usd: float = 0.10) -> BudgetStatus:
        if not self.enabled:
            return BudgetStatus(False, self.monthly_budget_usd, None, None, self.safety_buffer_usd, self.enable_platform_hard_limit, "Budget guard disabled.")

        if self.enable_platform_hard_limit and not self._hard_limit_attempted:
            self.set_platform_hard_limit()

        status = self.status()
        if status.current_usage_usd is None or status.remaining_usd is None:
            if self.fail_closed:
                raise BudgetExceededError(
                    f"Budget guard cannot verify current Apify usage before running {label}. Run blocked to avoid unexpected costs."
                )
            return status

        allowed_remaining = status.remaining_usd - status.safety_buffer_usd
        if allowed_remaining <= 0:
            raise BudgetExceededError(
                f"Monthly Apify budget reached. Current usage: ${status.current_usage_usd:.2f}, "
                f"budget: ${status.budget_usd:.2f}. Skipping {label}."
            )
        if estimated_cost_usd > allowed_remaining:
            raise BudgetExceededError(
                f"Skipping {label}: estimated run cost ${estimated_cost_usd:.2f} may exceed remaining safe budget "
                f"${allowed_remaining:.2f}. Current usage: ${status.current_usage_usd:.2f}, budget: ${status.budget_usd:.2f}."
            )
        return status
