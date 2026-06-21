# Completion status

An honest map of what this repo can and cannot do, so nobody mistakes a runnable
demo for a funded live-trading system.

## ✅ Complete and runnable now (demo / testnet grade)

- **Auth + users + roles** — SQL-backed (`auth_service`, SQLAlchemy, Postgres in
  Docker / SQLite locally). Signup, login, refresh, `/me`; bcrypt hashing; JWT
  access+refresh. **USER/ADMIN roles** with admin-only user management
  (list / promote / disable). Replaces the prior BigQuery-as-user-store. Tested.
- **Dashboard frontend** (`frontend`, Next.js) — login, signup, dashboard
  (balances, positions, risk snapshot, order ticket, kill-switch), and an
  **admin panel**. Coherent auth context, a real API client, and a working route
  guard (`withAuth`) — the previously-missing import that broke the build.
  `next build` passes.
- **Execution engine** — unified, paper/testnet/live via an adapter, real
  HMAC-signed Binance path, symbol-filter rounding, real pre-trade risk limits,
  Redis kill-switch, TWAP/VWAP. Tested. (See `execution_path_gap_analysis.md`.)
- **One-command local stack** — `docker compose up --build` runs db + redis +
  auth + execution + dashboard together.

## ⚠️ Not production-ready (intentionally)

These are real, and shipping as if they were done would be dangerous:

- **Live trading is gated off by default** (paper mode). Do not enable live until
  the execution follow-ups land (fill reconciliation via user-data WebSocket,
  persistent risk state, idempotency/recovery). See `tracking_issues.md`.
- **Secrets** — JWT secret and exchange keys read from env. Move to Secret
  Manager before any real deployment.
- **Refresh-token revocation** — refresh tokens are stateless JWTs; there is no
  server-side revocation/rotation store yet.
- **ML pipeline** (`model_pipeline`, `model_gateway`, `data_pipeline`) — scaffolded,
  not trained/validated. The execution engine treats predictions as optional.
- **Mobile app** (`mobile`) — scaffold only.
- **Migrations** — auth uses `create_all`; add Alembic before schema evolves in prod.
- **Connectors beyond Binance spot / Uniswap stubs**, OANDA/FX, and the latency
  budget harness remain TODO.

## Where to look

- Local run guide: `docs/running_locally.md`
- Execution internals + remaining gaps: `docs/execution_path_gap_analysis.md`
- Follow-up issues to open: `tracking_issues.md` (in the PR artifacts)
