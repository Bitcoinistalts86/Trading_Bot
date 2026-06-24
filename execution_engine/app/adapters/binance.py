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
from decimal import Decimal

import httpx

from ..config import ExecutionMode, Settings
from ..models import Execution, Order, OrderType, Side
from ..reconciliation.position_store import PositionStore
from .filters import SymbolFilters, fmt

logger = logging.getLogger("execution_engine.adapter.binance")

_BASE_URLS = {
    ExecutionMode.TESTNET: "https://testnet.binance.vision",
    ExecutionMode.LIVE: "https://api.binance.com",
}

_WS_BASE_URLS = {
    ExecutionMode.TESTNET: "wss://testnet.binance.vision",
    ExecutionMode.LIVE: "wss://stream.binance.com:9443",
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
        self._filters: dict[str, SymbolFilters] = {}
        # Reconciliation: authoritative balances/orders from the user-data stream.
        self.store = PositionStore()
        self._user_stream = None

    async def _get_filters(self, instrument: str) -> SymbolFilters | None:
        """Fetch + cache a symbol's trading filters from exchangeInfo (best effort)."""
        sym = instrument.upper()
        if sym in self._filters:
            return self._filters[sym]
        try:
            r = await self._client.get("/api/v3/exchangeInfo", params={"symbol": sym})
            r.raise_for_status()
            symbols = r.json().get("symbols", [])
            if not symbols:
                return None
            filt = SymbolFilters.from_symbol_info(symbols[0])
            self._filters[sym] = filt
            return filt
        except Exception as exc:  # noqa: BLE001 -- degrade to unrounded send
            logger.warning("Could not load filters for %s (%s); sending unrounded.", sym, exc)
            return None

    async def start_user_stream(self, on_fill=None) -> None:
        """Seed the store from REST, then keep it live via the user-data WS."""
        # Seed first so positions are correct immediately, before the first event.
        try:
            balances = await self._raw_account_balances()
            open_orders = await self._open_orders()
            self.store.seed(balances, open_orders)
            logger.info("Seeded position store: %d assets, %d open orders",
                        len(balances), len(open_orders))
        except Exception as exc:  # noqa: BLE001 -- degrade to REST reads
            logger.warning("Could not seed position store (%s); REST fallback active.", exc)

        try:
            from ..reconciliation.binance_user_stream import BinanceUserDataStream
            ws_base = _WS_BASE_URLS[self.settings.mode]
            self._user_stream = BinanceUserDataStream(
                self._client, self._key, ws_base, self.store, on_fill=on_fill,
            )
            await self._user_stream.start()
        except Exception as exc:  # noqa: BLE001
            logger.warning("User-data stream unavailable (%s); REST fallback active.", exc)

    async def _open_orders(self) -> list[dict]:
        params = {"timestamp": self._timestamp(), "recvWindow": 5000}
        r = await self._client.get(
            "/api/v3/openOrders", params=urllib.parse.parse_qsl(self._sign(params)),
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    async def _raw_account_balances(self) -> list[dict]:
        params = {"timestamp": self._timestamp(), "recvWindow": 5000}
        r = await self._client.get(
            "/api/v3/account", params=urllib.parse.parse_qsl(self._sign(params)),
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json().get("balances", [])
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
        # Prefer the reconciled store (kept live by the user-data stream).
        if self.store.seeded:
            return self.store.free_balances()
        return await self._rest_balances()

    async def _rest_balances(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for bal in await self._raw_account_balances():
            free = float(bal["free"])
            if free > 0:
                out[bal["asset"]] = free
        return out

    # Conditional order types -> Binance order types.
    _COND_TYPE_MAP = {
        OrderType.STOP_LOSS: "STOP_LOSS",
        OrderType.STOP_LIMIT: "STOP_LOSS_LIMIT",
        OrderType.TAKE_PROFIT: "TAKE_PROFIT",
        OrderType.TAKE_PROFIT_LIMIT: "TAKE_PROFIT_LIMIT",
    }
    _LIMIT_STYLE = {OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT_LIMIT}

    # --- order submission ---------------------------------------------------
    async def place_order(self, order: Order, ref_price: float) -> Execution:
        is_limit = order.order_type in self._LIMIT_STYLE
        has_stop = order.order_type in self._COND_TYPE_MAP
        # The limit price for a *_LIMIT order is `price`, or `stop_limit_price` for stops.
        limit_price = order.price if order.order_type == OrderType.LIMIT else order.stop_limit_price
        if is_limit and not limit_price:
            raise ValueError(f"{order.order_type.value} requires a limit price.")
        if has_stop and not order.stop_price:
            raise ValueError(f"{order.order_type.value} requires a stop_price.")

        # Round onto the symbol's valid grid before signing.
        filt = await self._get_filters(order.instrument)
        stop_str = None
        if filt is not None:
            qty_dec = filt.round_quantity(order.quantity)
            price_dec = filt.round_price(limit_price) if is_limit else None
            stop_dec = filt.round_price(order.stop_price) if has_stop else None
            notional_ref = price_dec if is_limit else (stop_dec if has_stop else Decimal(str(ref_price)))
            reason = filt.validate(qty_dec, notional_ref)
            if reason:
                logger.warning("Order %s violates symbol filters: %s", order.client_order_id, reason)
                return Execution(
                    order_id=order.client_order_id, exchange=self.name, instrument=order.instrument,
                    side=order.side, price=float(notional_ref), quantity=0.0,
                    status=f"REJECTED:{reason}", correlation_id=order.correlation_id,
                )
            qty_str = fmt(qty_dec, filt.qty_decimals)
            price_str = fmt(price_dec, filt.price_decimals) if is_limit else None
            stop_str = fmt(stop_dec, filt.price_decimals) if has_stop else None
        else:
            qty_str = _fmt(order.quantity)
            price_str = _fmt(limit_price) if is_limit else None
            stop_str = _fmt(order.stop_price) if has_stop else None

        binance_type = (
            self._COND_TYPE_MAP[order.order_type] if has_stop
            else ("LIMIT" if is_limit else "MARKET")
        )
        params = {
            "symbol": order.instrument.upper(),
            "side": order.side.value,
            "type": binance_type,
            "quantity": qty_str,
            "newClientOrderId": order.client_order_id,
            "newOrderRespType": "FULL",
            "timestamp": self._timestamp(),
            "recvWindow": 5000,
        }
        if is_limit:
            params["price"] = price_str
            params["timeInForce"] = "GTC"
        if has_stop:
            params["stopPrice"] = stop_str

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

    async def place_oco(self, order: Order, ref_price: float) -> list[Execution]:
        """Submit a native Binance OCO (take-profit limit + stop-limit)."""
        if not (order.tp_price and order.stop_price):
            raise ValueError("OCO requires tp_price and stop_price")
        filt = await self._get_filters(order.instrument)
        if filt is not None:
            qty_s = fmt(filt.round_quantity(order.quantity), filt.qty_decimals)
            tp_s = fmt(filt.round_price(order.tp_price), filt.price_decimals)
            stop_s = fmt(filt.round_price(order.stop_price), filt.price_decimals)
            stop_limit_s = fmt(filt.round_price(order.stop_limit_price or order.stop_price), filt.price_decimals)
        else:
            qty_s, tp_s, stop_s = _fmt(order.quantity), _fmt(order.tp_price), _fmt(order.stop_price)
            stop_limit_s = _fmt(order.stop_limit_price or order.stop_price)

        params = {
            "symbol": order.instrument.upper(), "side": order.side.value, "quantity": qty_s,
            "price": tp_s,                       # take-profit limit leg
            "stopPrice": stop_s,                 # stop trigger
            "stopLimitPrice": stop_limit_s, "stopLimitTimeInForce": "GTC",
            "listClientOrderId": order.client_order_id,
            "newOrderRespType": "FULL", "timestamp": self._timestamp(), "recvWindow": 5000,
        }
        body = self._sign(params)
        r = await self._client.post(
            "/api/v3/order/oco", content=body,
            headers={**self._headers(), "Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code >= 400:
            logger.error("Binance OCO rejected (%s): %s", r.status_code, r.text)
            return [Execution(order_id=order.client_order_id, exchange=self.name,
                              instrument=order.instrument, side=order.side, price=ref_price,
                              quantity=0.0, status="REJECTED", correlation_id=order.correlation_id)]
        reports = r.json().get("orderReports", [])
        return [Execution(order_id=str(rep.get("orderId", order.client_order_id)), exchange=self.name,
                          instrument=order.instrument, side=order.side,
                          price=float(rep.get("price", 0) or rep.get("stopPrice", 0) or 0),
                          quantity=0.0, status=rep.get("status", "NEW"),
                          correlation_id=order.correlation_id) for rep in reports] or \
               [Execution(order_id=order.client_order_id, exchange=self.name, instrument=order.instrument,
                          side=order.side, price=order.tp_price, quantity=0.0, status="NEW",
                          correlation_id=order.correlation_id)]

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
        if self._user_stream:
            await self._user_stream.stop()
        await self._client.aclose()


def _fmt(value: float) -> str:
    # Binance rejects scientific notation; send a plain decimal string.
    return f"{value:.8f}".rstrip("0").rstrip(".")
