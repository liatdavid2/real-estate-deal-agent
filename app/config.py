from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            name = match.group(1)
            default = match.group(2) or ""
            return os.getenv(name, default)
        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


class SourceConfig(BaseModel):
    name: str
    actor_id: str
    limit: int = 100
    estimated_cost_usd: float = 0.10
    run_input: dict[str, Any] = Field(default_factory=dict)


class SearchProfile(BaseModel):
    name: str
    enabled: bool = True
    description: str = ""
    transaction: str = "unknown"
    filters: dict[str, Any] = Field(default_factory=dict)
    scoring: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceConfig]


class AppConfig(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)
    profiles: list[SearchProfile]


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data = _expand_env(data)
    return AppConfig.model_validate(data)
