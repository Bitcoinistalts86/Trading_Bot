# execution_engine/app/adapters/binance.py
"""
Binance Spot adapter -- the real, signed execution path that both legacy engines
were missing entirely (neither had any HMAC signing or order submission).

Uses Binance's official REST API. Requests to the order endpoint are signed with
HMAC-SHA256 over the query string, per the Binance signed-endpoint spec, and the
API key travels in the `X-MBX-APIKEY` header.

Base URLs:
  * testnet:  https://testnet.binance.vision
  * live:     https://api.binance.com

Notes / deliberate scope:
  * MARKET and LIMIT are submitted natively. TWAP/VWAP are sliced upstream by the
    Executor into child MARKET orders, so this adapter only ever sees primitives.
  * `recvWindow` + server-time-aware timestamps guard against clock skew.
  * This adapter never decides *whether* to trade -- risk + kill-switch checks run
    before it is ever called.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
import urllib.parse

import httpx

from ..config import ExecutionMode, Settings
from ..models import Execution, Order, OrderType, Side

logger = logging.getLogger("execution_engine.adapter.binance")

_BASE_URLS = {
    ExecutionMode.TESTNET: "https://testnet.binance.vision",
    ExecutionMode.LIVE: "https://api.binance.com",
}


class BinanceAdapter:
    name = "binance"

    def __init__(self, settings: Settings) -> None:
        if settings.mode not in _BASE_URLS:
            raise ValueError(f"BinanceAdapter requires TESTNET or LIVE mode, got {settings.mode}")
        if not (settings.binance_api_key and settings.binance_api_secret):
            raise ValueError("BinanceAdapter requires API key and secret.")
        self.settings = settings
        self.base_url = _BASE_URLS[settings.mode]
        self._key = settings.binance_api_key
        self._secret = settings.binance_api_secret.encode()
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
        self._time_offset_ms = 0

    # --- signing helpers ----------------------------------------------------
    def _sign(self, params: dict) -> str:
        query = urllib.parse.urlencode(params)
        sig = hmac.new(self._secret, query.encode(), hashlib.sha256).hexdigest()
        return f"{query}&signature={sig}"

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self._key}

    async def sync_time(self) -> None:
        """Align local clock with the server to avoid -1021 timestamp errors."""
        try:
            r = await self._client.get("/api/v3/time")
            r.raise_for_status()
            server_ms = r.json()["serverTime"]
            self._time_offset_ms = server_ms - int(time.time() * 1000)
            logger.info("Binance time offset: %d ms", self._time_offset_ms)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not sync Binance server time: %s", exc)

    def _timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset_ms

    # --- market data --------------------------------------------------------
    async def get_mark_price(self, instrument: str) -> float:
        r = await self._client.get("/api/v3/ticker/price", params={"symbol": instrument.upper()})
        r.raise_for_status()
        return float(r.json()["price"])

    async def get_balances(self) -> dict[str, float]:
        params = {"timestamp": self._timestamp(), "recvWindow": 5000}
        r = await self._client.get(
            "/api/v3/account", params=urllib.parse.parse_qsl(self._sign(params)),
            headers=self._headers(),
        )
        r.raise_for_status()
        out: dict[str, float] = {}
        for bal in r.json().get("balances", []):
            free = float(bal["free"])
            if free > 0:
                out[bal["asset"]] = free
        return out

    # --- order submission ---------------------------------------------------
    async def place_order(self, order: Order, ref_price: float) -> Execution:
        params = {
            "symbol": order.instrument.upper(),
            "side": order.side.value,
            "type": "MARKET" if order.order_type in (OrderType.MARKET, OrderType.TWAP, OrderType.VWAP) else "LIMIT",
            "quantity": _fmt(order.quantity),
            "newClientOrderId": order.client_order_id,
            "newOrderRespType": "FULL",
            "timestamp": self._timestamp(),
            "recvWindow": 5000,
        }
        if params["type"] == "LIMIT":
            if not order.price:
                raise ValueError("LIMIT order requires a price.")
            params["price"] = _fmt(order.price)
            params["timeInForce"] = "GTC"

        body = self._sign(params)
        r = await self._client.post(
            "/api/v3/order", content=body,
            headers={**self._headers(), "Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code >= 400:
            logger.error("Binance order rejected (%s): %s", r.status_code, r.text)
            return Execution(
                order_id=order.client_order_id, exchange=self.name, instrument=order.instrument,
                side=order.side, price=order.price or ref_price, quantity=0.0,
                status="REJECTED", correlation_id=order.correlation_id,
            )
        data = r.json()
        return self._parse_execution(order, data, ref_price)

    def _parse_execution(self, order: Order, data: dict, ref_price: float) -> Execution:
        fills = data.get("fills", []) or []
        filled_qty = sum(float(f["qty"]) for f in fills) or float(data.get("executedQty", 0) or 0)
        fees = sum(float(f.get("commission", 0)) for f in fills)
        if fills:
            notional = sum(float(f["price"]) * float(f["qty"]) for f in fills)
            avg_price = notional / filled_qty if filled_qty else (order.price or ref_price)
        else:
            avg_price = order.price or ref_price
        return Execution(
            order_id=str(data.get("orderId", order.client_order_id)),
            exchange=self.name,
            instrument=order.instrument,
            side=order.side,
            price=avg_price,
            quantity=filled_qty,
            fees=fees,
            status=data.get("status", "FILLED"),
            correlation_id=order.correlation_id,
        )

    async def close(self) -> None:
        await self._client.aclose()


def _fmt(value: float) -> str:
    # Binance rejects scientific notation; send a plain decimal string.
    return f"{value:.8f}".rstrip("0").rstrip(".")
