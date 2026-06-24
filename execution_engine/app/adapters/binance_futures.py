# execution_engine/app/adapters/binance_futures.py
"""
Binance USD-M Futures adapter (`fapi`).

Implements the same ExchangeAdapter interface as the spot adapter, so the
executor / risk / PnL code is unchanged. Differences from spot:
  * base URLs: testnet `testnet.binancefuture.com`, live `fapi.binance.com`
  * mark price from `/fapi/v1/premiumIndex`
  * balances from `/fapi/v2/balance`
  * leverage + margin type configured per symbol on startup
  * conditional order types map to futures' `STOP` / `STOP_MARKET` /
    `TAKE_PROFIT` / `TAKE_PROFIT_MARKET`

Scope of this first slice: one-way position mode, signed REST order placement,
leverage/margin setup, and futures symbol-filter rounding (reuses `SymbolFilters`).
**Validate against the futures testnet before any live use.** Not yet included
(see docs/SYSTEM_UPGRADES.md): the futures user-data stream (`ACCOUNT_UPDATE` /
`ORDER_TRADE_UPDATE`) for reconciliation, hedge mode, funding in PnL, and
liquidation-distance risk.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
import urllib.parse
from decimal import Decimal

import httpx

from ..config import ExecutionMode, Settings
from ..models import Execution, Order, OrderType, Side
from .filters import SymbolFilters, fmt

logger = logging.getLogger("execution_engine.adapter.binance_futures")

_BASE_URLS = {
    ExecutionMode.TESTNET: "https://testnet.binancefuture.com",
    ExecutionMode.LIVE: "https://fapi.binance.com",
}

# Our order types -> Binance Futures order types.
_FUTURES_TYPE = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.STOP_LOSS: "STOP_MARKET",
    OrderType.STOP_LIMIT: "STOP",
    OrderType.TAKE_PROFIT: "TAKE_PROFIT_MARKET",
    OrderType.TAKE_PROFIT_LIMIT: "TAKE_PROFIT",
}
_LIMIT_STYLE = {OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT_LIMIT}
_HAS_STOP = {OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT, OrderType.TAKE_PROFIT_LIMIT}


def futures_order_type(order_type: OrderType) -> str:
    return _FUTURES_TYPE.get(order_type, "MARKET")


class FuturesBinanceAdapter:
    name = "binance-futures"

    def __init__(self, settings: Settings) -> None:
        if settings.mode not in _BASE_URLS:
            raise ValueError("FuturesBinanceAdapter requires TESTNET or LIVE mode")
        if not (settings.binance_api_key and settings.binance_api_secret):
            raise ValueError("FuturesBinanceAdapter requires API key and secret.")
        self.settings = settings
        self.base_url = _BASE_URLS[settings.mode]
        self._key = settings.binance_api_key
        self._secret = settings.binance_api_secret.encode()
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
        self._time_offset_ms = 0
        self._filters: dict[str, SymbolFilters] = {}

    # --- signing ------------------------------------------------------------
    def _sign(self, params: dict) -> str:
        query = urllib.parse.urlencode(params)
        sig = hmac.new(self._secret, query.encode(), hashlib.sha256).hexdigest()
        return f"{query}&signature={sig}"

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self._key}

    def _timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset_ms

    async def sync_time(self) -> None:
        try:
            r = await self._client.get("/fapi/v1/time")
            r.raise_for_status()
            self._time_offset_ms = r.json()["serverTime"] - int(time.time() * 1000)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not sync futures server time: %s", exc)

    # --- setup --------------------------------------------------------------
    async def configure(self) -> None:
        """Set leverage + margin type for the configured symbols (best effort)."""
        for sym in [s.strip().upper() for s in self.settings.futures_symbols.split(",") if s.strip()]:
            await self._set_leverage(sym, self.settings.futures_leverage)
            await self._set_margin_type(sym, self.settings.futures_margin_type)

    async def _post_signed(self, path: str, params: dict) -> httpx.Response:
        params = {**params, "timestamp": self._timestamp(), "recvWindow": 5000}
        return await self._client.post(
            path, content=self._sign(params),
            headers={**self._headers(), "Content-Type": "application/x-www-form-urlencoded"},
        )

    async def _set_leverage(self, symbol: str, leverage: int) -> None:
        try:
            r = await self._post_signed("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})
            if r.status_code >= 400:
                logger.warning("Set leverage %s=%d failed: %s", symbol, leverage, r.text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Set leverage error: %s", exc)

    async def _set_margin_type(self, symbol: str, margin_type: str) -> None:
        try:
            r = await self._post_signed("/fapi/v1/marginType",
                                        {"symbol": symbol, "marginType": margin_type.upper()})
            # -4046 "No need to change margin type" is fine.
            if r.status_code >= 400 and "-4046" not in r.text:
                logger.warning("Set margin %s=%s failed: %s", symbol, margin_type, r.text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Set margin error: %s", exc)

    async def _get_filters(self, instrument: str) -> SymbolFilters | None:
        sym = instrument.upper()
        if sym in self._filters:
            return self._filters[sym]
        try:
            r = await self._client.get("/fapi/v1/exchangeInfo")
            r.raise_for_status()
            for info in r.json().get("symbols", []):
                if info["symbol"] == sym:
                    self._filters[sym] = SymbolFilters.from_symbol_info(info)
                    return self._filters[sym]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load futures filters for %s (%s).", sym, exc)
        return None

    # --- market data --------------------------------------------------------
    async def get_mark_price(self, instrument: str) -> float:
        r = await self._client.get("/fapi/v1/premiumIndex", params={"symbol": instrument.upper()})
        r.raise_for_status()
        return float(r.json()["markPrice"])

    async def get_balances(self) -> dict[str, float]:
        params = {"timestamp": self._timestamp(), "recvWindow": 5000}
        r = await self._client.get("/fapi/v2/balance",
                                   params=urllib.parse.parse_qsl(self._sign(params)),
                                   headers=self._headers())
        r.raise_for_status()
        return {b["asset"]: float(b["balance"]) for b in r.json() if float(b["balance"]) != 0}

    # --- order building (pure; unit-tested) ---------------------------------
    def build_order_params(self, order: Order, qty_str: str,
                           price_str: str | None, stop_str: str | None) -> dict:
        params = {
            "symbol": order.instrument.upper(),
            "side": order.side.value,
            "type": futures_order_type(order.order_type),
            "quantity": qty_str,
            "newClientOrderId": order.client_order_id,
            "newOrderRespType": "RESULT",
        }
        if order.order_type in _LIMIT_STYLE:
            params["price"] = price_str
            params["timeInForce"] = "GTC"
        if order.order_type in _HAS_STOP:
            params["stopPrice"] = stop_str
        return params

    # --- order submission ---------------------------------------------------
    async def place_order(self, order: Order, ref_price: float) -> Execution:
        is_limit = order.order_type in _LIMIT_STYLE
        has_stop = order.order_type in _HAS_STOP
        limit_price = order.price if order.order_type == OrderType.LIMIT else order.stop_limit_price

        filt = await self._get_filters(order.instrument)
        if filt is not None:
            qty_dec = filt.round_quantity(order.quantity)
            ref_for_validate = filt.round_price(limit_price) if (is_limit and limit_price) else Decimal(str(ref_price))
            reason = filt.validate(qty_dec, ref_for_validate)
            if reason:
                return Execution(order_id=order.client_order_id, exchange=self.name,
                                 instrument=order.instrument, side=order.side, price=float(ref_for_validate),
                                 quantity=0.0, status=f"REJECTED:{reason}", correlation_id=order.correlation_id)
            qty_str = fmt(qty_dec, filt.qty_decimals)
            price_str = fmt(filt.round_price(limit_price), filt.price_decimals) if (is_limit and limit_price) else None
            stop_str = fmt(filt.round_price(order.stop_price), filt.price_decimals) if has_stop else None
        else:
            qty_str = str(order.quantity)
            price_str = str(limit_price) if is_limit else None
            stop_str = str(order.stop_price) if has_stop else None

        params = self.build_order_params(order, qty_str, price_str, stop_str)
        r = await self._post_signed("/fapi/v1/order", params)
        if r.status_code >= 400:
            logger.error("Futures order rejected (%s): %s", r.status_code, r.text)
            return Execution(order_id=order.client_order_id, exchange=self.name,
                             instrument=order.instrument, side=order.side, price=ref_price,
                             quantity=0.0, status="REJECTED", correlation_id=order.correlation_id)
        data = r.json()
        filled = float(data.get("executedQty", 0) or 0)
        avg = float(data.get("avgPrice", 0) or 0) or (limit_price or ref_price)
        return Execution(order_id=str(data.get("orderId", order.client_order_id)), exchange=self.name,
                         instrument=order.instrument, side=order.side, price=avg, quantity=filled,
                         status=data.get("status", "NEW"), correlation_id=order.correlation_id)

    async def close(self) -> None:
        await self._client.aclose()
