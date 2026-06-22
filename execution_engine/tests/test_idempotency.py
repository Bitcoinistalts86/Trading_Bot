# execution_engine/tests/test_idempotency.py
"""Offline tests for idempotency / duplicate-order protection."""
import asyncio
import re

import pytest

from execution_engine.app.idempotency import (
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
    deterministic_client_order_id,
    run_idempotent,
)
from execution_engine.app.models import OrderType, Side, Signal

try:
    import fakeredis.aioredis as _fakeredis
    _HAS_FAKEREDIS = True
except ImportError:
    _HAS_FAKEREDIS = False

_BINANCE_COID = re.compile(r"^[A-Za-z0-9\-_.:/]{1,36}$")


def _stores():
    stores = [InMemoryIdempotencyStore()]
    if _HAS_FAKEREDIS:
        stores.append(RedisIdempotencyStore(_fakeredis.FakeRedis(decode_responses=True)))
    return stores


def test_deterministic_client_order_id_is_stable_and_valid():
    a = deterministic_client_order_id("intent-123")
    b = deterministic_client_order_id("intent-123")
    c = deterministic_client_order_id("intent-999")
    assert a == b                      # same key -> same id (exchange dedup works)
    assert a != c                      # different key -> different id
    assert _BINANCE_COID.match(a)      # valid Binance clientOrderId


def test_store_claims_once():
    for store in _stores():
        async def run():
            is_new, prior = await store.begin("k1", ttl=60)
            assert is_new and prior is None
            again_new, again_prior = await store.begin("k1", ttl=60)
            assert not again_new                       # second claim is a duplicate
            assert again_prior["status"] == "PENDING"
            await store.complete("k1", {"n_fills": 3}, ttl=60)
            _, done = await store.begin("k1", ttl=60)
            assert done["status"] == "DONE" and done["n_fills"] == 3
        asyncio.run(run())


def test_run_idempotent_executes_once():
    for store in _stores():
        async def run():
            calls = {"n": 0}

            async def fn():
                calls["n"] += 1
                return {"fills": 1}

            executed1, _ = await run_idempotent(store, "order-A", 60, fn)
            executed2, prior = await run_idempotent(store, "order-A", 60, fn)
            assert executed1 is True
            assert executed2 is False         # duplicate suppressed
            assert calls["n"] == 1            # fn ran exactly once
        asyncio.run(run())


def test_signal_propagates_idempotency_key_to_order():
    sig = Signal(instrument="BTCUSDT", side=Side.BUY, quantity=0.01,
                 order_type=OrderType.MARKET, idempotency_key="abc-123")
    order = sig.to_order()
    assert order.idempotency_key == "abc-123"
    assert order.effective_idempotency_key() == "abc-123"


def test_effective_key_falls_back_to_correlation_id():
    sig = Signal(instrument="BTCUSDT", side=Side.BUY, quantity=0.01, correlation_id="corr-7")
    order = sig.to_order()
    assert order.effective_idempotency_key() == "corr-7"
