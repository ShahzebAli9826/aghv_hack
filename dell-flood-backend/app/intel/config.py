"""Environment parsing for web intelligence. Parsed once into a frozen object."""
from __future__ import annotations

import logging
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

log = logging.getLogger("aegis.intel.config")


class Mode(StrEnum):
    live = "live"
    replay = "replay"
    disabled = "disabled"


@dataclass(frozen=True)
class Settings:
    mode: Mode
    api_key: str | None = field(default=None, repr=False)
    agent_base_url: str = "https://agent.tinyfish.ai"
    search_base_url: str = "https://api.search.tinyfish.ai"
    fetch_base_url: str = "https://api.fetch.tinyfish.ai"
    max_concurrent_agent_runs: int = 2
    usd_per_step: float = 0.016
    max_usd_per_request: float = 0.50
    max_steps_per_run: int = 30
    run_timeout_s: float = 180.0
    poll_interval_s: float = 3.0
    http_timeout_s: float = 30.0
    max_retry_wait_s: float = 120.0
    allow_unverified_sources: bool = False
    webhook_token: str | None = field(default=None, repr=False)
    public_base_url: str | None = None
    imd_api_key: str | None = field(default=None, repr=False)
    task_workers: int = 6

    @property
    def enabled(self) -> bool:
        return self.mode is not Mode.disabled

    def limits(self) -> dict:
        return {
            "max_concurrent_agent_runs": self.max_concurrent_agent_runs,
            "usd_per_step": self.usd_per_step,
            "max_usd_per_request": self.max_usd_per_request,
            "max_steps_per_run": self.max_steps_per_run,
            "run_timeout_s": self.run_timeout_s,
            "allow_unverified_sources": self.allow_unverified_sources,
        }


def _text(env: Mapping[str, str], name: str) -> str | None:
    value = (env.get(name) or "").strip()
    return value or None


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    value = _text(env, name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _number(env: Mapping[str, str], name: str, default: float, low: float, high: float) -> float:
    value = _text(env, name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        parsed = math.nan
    if not math.isfinite(parsed):
        log.warning("%s is not a finite number; using %s", name, default)
        return default
    return min(max(parsed, low), high)


def _price(env: Mapping[str, str], name: str, default: float, high: float) -> float:
    """A zero or negative price would switch the budget cap off, so it falls back to the default."""
    parsed = _number(env, name, default, -math.inf, high)
    if parsed <= 0:
        log.warning("%s must be positive; using %s", name, default)
        return default
    return parsed


def _https_url(env: Mapping[str, str], name: str) -> str | None:
    value = _text(env, name)
    if value and value.lower().startswith("https://"):
        return value.rstrip("/")
    return None


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    api_key = _text(env, "TINYFISH_API_KEY")
    enabled_flag = _flag(env, "TINYFISH_ENABLED", True)

    requested = (_text(env, "TINYFISH_MODE") or "").lower()
    if requested == Mode.replay:
        mode = Mode.replay
    elif requested == Mode.disabled or not enabled_flag:
        mode = Mode.disabled
    else:
        mode = Mode.live if api_key else Mode.disabled

    return Settings(
        mode=mode,
        api_key=api_key if mode is Mode.live else None,
        agent_base_url=_https_url(env, "TINYFISH_AGENT_BASE_URL") or "https://agent.tinyfish.ai",
        max_concurrent_agent_runs=int(_number(env, "TINYFISH_MAX_CONCURRENT_AGENT_RUNS", 2, 1, 10)),
        usd_per_step=_price(env, "TINYFISH_USD_PER_STEP", 0.016, 10.0),
        max_usd_per_request=_number(env, "TINYFISH_MAX_USD_PER_REQUEST", 0.50, 0.0, 100.0),
        max_steps_per_run=int(_number(env, "TINYFISH_MAX_STEPS_PER_RUN", 30, 1, 500)),
        run_timeout_s=_number(env, "TINYFISH_RUN_TIMEOUT_S", 180.0, 5.0, 3600.0),
        poll_interval_s=_number(env, "TINYFISH_POLL_INTERVAL_S", 3.0, 0.0, 60.0),
        allow_unverified_sources=_flag(env, "TINYFISH_ALLOW_UNVERIFIED_SOURCES", False),
        webhook_token=_text(env, "TINYFISH_WEBHOOK_TOKEN"),
        public_base_url=_https_url(env, "TINYFISH_PUBLIC_BASE_URL"),
        imd_api_key=_text(env, "IMD_API_KEY"),
    )
