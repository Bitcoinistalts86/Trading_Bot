# execution_engine/app/reconciliation/binance_user_stream.py
"""
Binance user-data stream manager.

Lifecycle:
  1. POST /api/v3/userDataStream            -> obtain a listenKey (API-key auth)
  2. connect wss://.../ws/<listenKey>       -> receive account/order events
  3. PUT  /api/v3/userDataStream (keepalive) every ~30 min
  4. DELETE /api/v3/userDataStream on shutdown

Events are dispatched into a PositionStore. On any disconnect the manager
recreates the listenKey and reconnects, so the store self-heals.
"""
from __future__ import annotations

import asyncio
import json
import logging

import httpx
import websockets

from .position_store import PositionStore

logger = logging.getLogger("execution_engine.user_stream")

KEEPALIVE_INTERVAL_S = 30 * 60  # Binance expires a listenKey after 60 min


class BinanceUserDataStream:
    def __init__(self, rest: httpx.AsyncClient, api_key: str, ws_base: str,
                 store: PositionStore, on_fill=None) -> None:
        self._rest = rest
        self._key = api_key
        self._ws_base = ws_base.rstrip("/")
        self.store = store
        self._on_fill = on_fill           # optional async callback(fill_dict)
        self._listen_key: str | None = None
        self._task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    # --- listenKey REST -----------------------------------------------------
    async def _create_listen_key(self) -> str:
        r = await self._rest.post("/api/v3/userDataStream", headers={"X-MBX-APIKEY": self._key})
        r.raise_for_status()
        return r.json()["listenKey"]

    async def _keepalive_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=KEEPALIVE_INTERVAL_S)
            except asyncio.TimeoutError:
                pass
            if self._stop.is_set() or not self._listen_key:
                return
            try:
                await self._rest.put("/api/v3/userDataStream",
                                     params={"listenKey": self._listen_key},
                                     headers={"X-MBX-APIKEY": self._key})
                logger.debug("listenKey keepalive ok")
            except Exception as exc:  # noqa: BLE001
                logger.warning("listenKey keepalive failed: %s", exc)

    async def _close_listen_key(self) -> None:
        if not self._listen_key:
            return
        try:
            await self._rest.delete("/api/v3/userDataStream",
                                    params={"listenKey": self._listen_key},
                                    headers={"X-MBX-APIKEY": self._key})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to close listenKey: %s", exc)

    # --- dispatch -----------------------------------------------------------
    async def _dispatch(self, raw: str) -> None:
        event = json.loads(raw)
        etype = event.get("e")
        if etype == "outboundAccountPosition":
            self.store.apply_account_position(event)
        elif etype == "executionReport":
            fill = self.store.apply_execution_report(event)
            if fill and self._on_fill:
                await self._on_fill(fill)
        elif etype == "balanceUpdate":
            logger.debug("balanceUpdate: %s", event)  # delta event; snapshot follows

    # --- run loop -----------------------------------------------------------
    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._listen_key = await self._create_listen_key()
                url = f"{self._ws_base}/ws/{self._listen_key}"
                logger.info("Connecting user-data stream")
                async with websockets.connect(url, ping_interval=180) as ws:
                    self._keepalive_task = asyncio.create_task(self._keepalive_loop())
                    while not self._stop.is_set():
                        raw = await ws.recv()
                        await self._dispatch(raw)
            except Exception as exc:  # noqa: BLE001
                if self._stop.is_set():
                    break
                logger.warning("User-data stream error (%s); reconnecting in 5s", exc)
                await asyncio.sleep(5)
            finally:
                if self._keepalive_task:
                    self._keepalive_task.cancel()

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
        await self._close_listen_key()
