# Running the full stack locally

One command brings up Postgres, Redis, the auth service, the execution engine
(paper mode — no real orders), and the dashboard:

```bash
cp .env.example .env        # optional: edit JWT_SECRET / admin creds
docker compose up --build
```

Then open:

| Service            | URL                          |
|--------------------|------------------------------|
| Dashboard          | http://localhost:3000        |
| Auth API (docs)    | http://localhost:8000/docs   |
| Execution API (docs)| http://localhost:8080/docs  |

A bootstrap admin is created from `.env` on first boot
(`admin@example.com` / `adminpass` by default). Sign in with it to see the
**Admin** link (user management). New sign-ups are regular `USER`s.

## Running services individually (no Docker)

```bash
# Auth service (SQLite by default — zero config)
cd auth_service
pip install -r requirements.txt
uvicorn app.main:app --port 8000
python -m app.seed --email admin@example.com --password adminpass   # make an admin

# Execution engine (paper mode)
cd execution_engine
pip install -r requirements.txt
PYTHONPATH=.. uvicorn app.main:app --port 8080

# Frontend
cd frontend
npm install
NEXT_PUBLIC_AUTH_URL=http://localhost:8000 NEXT_PUBLIC_EXEC_URL=http://localhost:8080 npm run dev
```

## Tests

```bash
# Backend (offline)
PYTHONPATH=. python -m pytest auth_service/tests execution_engine/tests -q

# Frontend type-check + build
cd frontend && npm run build
```

## Switching the execution engine to testnet

Paper mode places no real orders. To exercise the real signed path against
Binance **testnet** (fake money), set on the `execution_engine` service:

```yaml
EXECUTION_MODE: testnet
BINANCE_API_KEY: <testnet key>
BINANCE_API_SECRET: <testnet secret>
```

Live mode additionally requires `I_UNDERSTAND_LIVE_TRADING=true` and is **not**
recommended until the items in `docs/COMPLETION_STATUS.md` are done.
