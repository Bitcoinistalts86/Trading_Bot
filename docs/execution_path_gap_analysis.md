# Execution Path: Gap Analysis & Reconciliation

This document does two things: (1) explains how the two duplicate execution
engines were reconciled into one, and (2) maps out exactly what was missing for
the execution path to be "real," what this change delivers, and what still
remains before pointing it at a funded account.

## 1. The problem we started with

There were **two** execution engines that disagreed with each other:

| | `execution_engine/main.py` (legacy A) | `execution_engine/app/main.py` (legacy B) |
|---|---|---|
| Order model | `Signal` / `Order` (proto-aligned) | `TradeSignal` (`user_id`, `correlation_id`) |
| "Execution" | mutate in-memory `STATE` dict | stubbed: `# ... rest is the same` |
| Kill-switch | plain `bool`, resets on restart, not shared | Redis multi-level (correct) but **broken import** |
| Risk | balance check only | not implemented |
| Imports | OK | `..libraries.observability` (missing) + wrong relative path |
| Runs? | yes (Dockerfile target) | **no** (import + missing deps) |
| Real orders | none (no signing, no API calls) | none |

Neither placed a real order anywhere. Legacy B couldn't even import.

## 2. Reconciliation

One engine now lives in the `execution_engine/app/` package. The good ideas from
each were merged; the dead code was deleted.

```
execution_engine/
  main.py                  # thin shim: `from app.main import app` (keeps Docker entrypoint)
  app/
    main.py                # FastAPI app, Pub/Sub subscriber, circuit breaker, endpoints
    config.py              # settings + EXECUTION_MODE safety gating
    models.py              # canonical Signal/Order/Execution (proto-aligned)
    risk.py                # real pre-trade RiskManager
    execution.py           # immediate / TWAP / VWAP, routed through the adapter
    kill_switch.py         # Redis multi-level switch + in-memory fallback
    sinks.py               # Pub/Sub execution stream + BigQuery audit ledger
    adapters/
      base.py              # ExchangeAdapter interface (the missing seam)
      paper.py             # simulation (default, safe) — replaces legacy STATE dict
      binance.py           # real HMAC-signed Binance Spot (testnet/live)
```

Decisions:
- **Canonical models win.** `contracts/trading.proto` is the source of truth;
  the operational fields legacy B needed (`user_id`, `correlation_id`) were
  folded into `Signal`/`Order`.
- **Redis multi-level kill-switch wins** over the boolean, with a working
  in-memory fallback so the engine still runs in tests/local without Redis.
- **The adapter seam** is what makes "real vs simulated" a config choice instead
  of a code fork: the executor, risk gate, and TWAP/VWAP code are identical in
  all modes.

## 3. What "make the execution path real" required

### Delivered in this change
- [x] **An order actually leaves the process.** `BinanceAdapter` submits
      HMAC-SHA256-signed `POST /api/v3/order` requests with `X-MBX-APIKEY`,
      `recvWindow`, and server-time-synced timestamps.
- [x] **Testnet-first.** `EXECUTION_MODE=testnet` hits `testnet.binance.vision`
      with real signing but no real funds.
- [x] **Live is gated.** Reaching `live` requires `EXECUTION_MODE=live` **and**
      real credentials **and** `I_UNDERSTAND_LIVE_TRADING=true`; missing any one
      silently downgrades to paper with a loud log. You cannot go live by
      accident.
- [x] **Real pre-trade risk:** order-notional cap, projected-position cap,
      per-minute rate limit, open-order cap, daily realized-loss cap, slippage
      guard — each returning a machine-readable rejection reason.
- [x] **TWAP/VWAP route through the venue** as sliced child orders, with the
      risk gate + kill-switch re-checked between every slice (a HARD kill aborts
      a running algo order mid-flight).
- [x] **Shared, multi-replica kill-switch** (Redis) instead of a per-process
      boolean.
- [x] **Audit + event sinks** (BigQuery ledger + Pub/Sub `exec.lifecycle`) with
      graceful no-op fallback when GCP is absent.
- [x] **It imports and is tested** (offline pytest suite covering fills, the
      risk gate, kill-switch, and TWAP slicing/abort).

### Still required before funded live trading (follow-ups)
These are deliberately **not** in this PR; they need real account context and
careful review:

1. ~~**Exchange symbol filters.**~~ ✅ **Done** (PR: binance-symbol-filters).
   `BinanceAdapter` now fetches `LOT_SIZE`/`PRICE_FILTER`/`NOTIONAL` from
   `GET /api/v3/exchangeInfo`, floors quantity to `stepSize`, rounds price to
   `tickSize` (Decimal-precise), and rejects sub-`minNotional` orders before
   signing instead of letting the exchange bounce them.
2. ~~**Fill reconciliation via the user-data WebSocket stream.**~~ ✅ **Done**
   (PR: fill-reconciliation). `BinanceAdapter` opens the user-data stream
   (`listenKey` create + 30-min keepalive + reconnect), seeds a `PositionStore`
   from `GET /api/v3/account` + `openOrders`, and applies `outboundAccountPosition`
   (authoritative balances) and `executionReport` (order lifecycle + fills).
   `/v1/positions` now reports exchange truth (`reconciled: true`), and the risk
   manager reads open-order count + positions from the store instead of local
   inference. New `/v1/reconciliation` endpoint exposes the live snapshot.
3. **Idempotency / dedup.** `client_order_id` is generated and sent, but there is
   no persistent store to dedupe retried signals or recover in-flight orders
   after a crash.
4. ~~**Persistent risk state.**~~ ✅ **Done** (PR: persistent-risk-state). The
   per-minute order-rate window and the daily realized-loss counter now live in
   Redis (`risk:orders` ZSET, `risk:pnl:{YYYYMMDD}` with TTL), shared across
   replicas and durable across restarts — so a crash no longer resets the
   daily-loss stand-down. In-memory fallback when Redis is absent. (Open-order
   count and positions already come from the reconciled PositionStore.)
5. **Secret management.** Keys are read from env. In production they should come
   from Secret Manager (the repo already uses it for the JWT secret), never env
   or image layers.
6. **Spot vs. Futures / margin.** This adapter is Spot. Futures (the connector
   already streams `fapi` data) needs `/fapi/v1/order`, leverage/position-mode
   handling, and liquidation-aware risk.
7. **Order types beyond MARKET/LIMIT.** No stop-loss, take-profit, or OCO yet —
   these are table stakes for risk-managed live trading.
8. **Real mark price wiring.** The executor reads `get_mark_price`; in paper mode
   this uses seeds. It should subscribe to the market-data pipeline's price feed
   rather than calling the ticker endpoint per order.
9. **Latency budget.** The `<100 ms` target in the README has no measurement
   harness; add timing around the signal→submit path and record to the existing
   `latency_metrics` Redis list.

## 4. How to run

```bash
# Paper (default, no creds, no network orders)
cd execution_engine && pip install -r requirements.txt
PYTHONPATH=.. uvicorn app.main:app --port 8080

# Testnet (real signed calls, fake money)
export EXECUTION_MODE=testnet
export BINANCE_API_KEY=...      # testnet.binance.vision key
export BINANCE_API_SECRET=...
PYTHONPATH=.. uvicorn app.main:app --port 8080

# Tests (offline)
PYTHONPATH=.. python -m pytest execution_engine/tests/test_engine.py -q
```

**Live trading is intentionally hard to enable and is not recommended until the
follow-ups above are done and the strategy has a track record on testnet.**
