# execution_engine/tests/test_redis_factory.py
"""The Redis builders must degrade to in-memory when no Redis is configured."""
import asyncio

from execution_engine.app.redis_factory import connect_redis
from execution_engine.app.kill_switch import build_kill_switch, _InMemoryKillSwitch
from execution_engine.app.risk_state import build_risk_state, InMemoryRiskState
from execution_engine.app.idempotency import build_idempotency_store, InMemoryIdempotencyStore


def test_connect_redis_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert asyncio.run(connect_redis("", 6379)) is None


def test_builders_fall_back_to_in_memory(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert isinstance(asyncio.run(build_kill_switch("", 6379)), _InMemoryKillSwitch)
    assert isinstance(asyncio.run(build_risk_state("", 6379)), InMemoryRiskState)
    assert isinstance(asyncio.run(build_idempotency_store("", 6379)), InMemoryIdempotencyStore)


def test_connect_redis_handles_bad_url_gracefully(monkeypatch):
    # An unreachable URL must return None, not raise (startup must never crash).
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6390")  # nothing listening
    assert asyncio.run(connect_redis()) is None
