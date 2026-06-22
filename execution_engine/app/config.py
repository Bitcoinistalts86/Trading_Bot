# execution_engine/app/config.py
"""
Central configuration for the execution engine.

The most important thing this module does is gate *live* trading behind an
explicit, deliberate opt-in. The default mode is PAPER. You cannot reach LIVE by
accident: it requires EXECUTION_MODE=live, real API credentials, AND
I_UNDERSTAND_LIVE_TRADING=true. Missing any of these downgrades the engine to
paper mode with a loud warning instead of silently sending real orders.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum

from .secrets import SecretResolver

logger = logging.getLogger("execution_engine.config")


class ExecutionMode(str, Enum):
    PAPER = "paper"        # in-memory simulation, no network orders
    TESTNET = "testnet"    # real signed calls to the exchange testnet
    LIVE = "live"          # real signed calls to production (real funds)


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class RiskLimits:
    """Hard limits enforced on every order before it can reach a venue."""
    max_order_notional_usd: float = field(default_factory=lambda: _f("RISK_MAX_ORDER_NOTIONAL_USD", 5_000.0))
    max_position_notional_usd: float = field(default_factory=lambda: _f("RISK_MAX_POSITION_NOTIONAL_USD", 25_000.0))
    max_open_orders: int = field(default_factory=lambda: _i("RISK_MAX_OPEN_ORDERS", 20))
    max_orders_per_minute: int = field(default_factory=lambda: _i("RISK_MAX_ORDERS_PER_MINUTE", 60))
    max_daily_loss_usd: float = field(default_factory=lambda: _f("RISK_MAX_DAILY_LOSS_USD", 2_500.0))
    max_slippage_bps: float = field(default_factory=lambda: _f("RISK_MAX_SLIPPAGE_BPS", 50.0))


@dataclass
class Settings:
    mode: ExecutionMode
    project_id: str = field(default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", "test-project"))
    region: str = field(default_factory=lambda: os.environ.get("REGION", "us-central1"))

    # Exchange
    exchange: str = field(default_factory=lambda: os.environ.get("EXCHANGE", "binance"))
    binance_api_key: str = field(default_factory=lambda: os.environ.get("BINANCE_API_KEY", ""))
    binance_api_secret: str = field(default_factory=lambda: os.environ.get("BINANCE_API_SECRET", ""))

    # Dependencies
    model_gateway_url: str = field(default_factory=lambda: os.environ.get("MODEL_GATEWAY_URL", ""))
    redis_host: str = field(default_factory=lambda: os.environ.get("REDIS_HOST", ""))
    redis_port: int = field(default_factory=lambda: _i("REDIS_PORT", 6379))
    signals_subscription: str = field(default_factory=lambda: os.environ.get("SIGNALS_SUBSCRIPTION", "signals.baseline.sub"))
    executions_topic: str = field(default_factory=lambda: os.environ.get("EXECUTIONS_TOPIC", "exec.lifecycle"))
    bq_trades_table: str = field(default_factory=lambda: os.environ.get("BQ_TRADES_TABLE", ""))  # e.g. proj.trading.trades
    idempotency_ttl_s: int = field(default_factory=lambda: _i("IDEMPOTENCY_TTL_S", 86_400))

    # Simulation defaults (paper mode)
    paper_starting_usd: float = field(default_factory=lambda: _f("PAPER_STARTING_USD", 100_000.0))
    paper_slippage_bps: float = field(default_factory=lambda: _f("PAPER_SLIPPAGE_BPS", 2.0))
    taker_fee_bps: float = field(default_factory=lambda: _f("TAKER_FEE_BPS", 7.5))

    limits: RiskLimits = field(default_factory=RiskLimits)

    @property
    def is_live(self) -> bool:
        return self.mode == ExecutionMode.LIVE

    @property
    def is_simulation(self) -> bool:
        return self.mode == ExecutionMode.PAPER


def load_settings() -> Settings:
    raw = os.environ.get("EXECUTION_MODE", "paper").strip().lower()
    try:
        mode = ExecutionMode(raw)
    except ValueError:
        logger.warning("Unknown EXECUTION_MODE=%r; defaulting to PAPER.", raw)
        mode = ExecutionMode.PAPER

    s = Settings(mode=mode)

    # Resolve exchange keys through Secret Manager (prod) or env (dev) before the
    # safety gate, so the gate sees the actually-available credentials.
    resolver = SecretResolver(s.project_id, os.environ.get("SECRETS_BACKEND", "env"))
    s.binance_api_key = resolver.get("BINANCE_API_KEY", secret_id="binance-api-key")
    s.binance_api_secret = resolver.get("BINANCE_API_SECRET", secret_id="binance-api-secret")

    # --- Safety gate: refuse to silently go live ------------------------------
    if mode in (ExecutionMode.LIVE, ExecutionMode.TESTNET):
        if not (s.binance_api_key and s.binance_api_secret):
            logger.error(
                "EXECUTION_MODE=%s requires BINANCE_API_KEY/BINANCE_API_SECRET. "
                "Falling back to PAPER mode.", mode.value,
            )
            s.mode = ExecutionMode.PAPER

    if s.mode == ExecutionMode.LIVE:
        consent = os.environ.get("I_UNDERSTAND_LIVE_TRADING", "").strip().lower()
        if consent != "true":
            logger.critical(
                "LIVE trading requested without explicit consent "
                "(set I_UNDERSTAND_LIVE_TRADING=true). Falling back to PAPER mode.",
            )
            s.mode = ExecutionMode.PAPER

    logger.warning("Execution engine starting in %s mode.", s.mode.value.upper())
    return s
