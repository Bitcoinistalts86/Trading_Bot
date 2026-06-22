# Deploying to Railway

This deploys the full stack as Railway services: **Postgres** + **Redis**
(managed plugins) and three app services — **auth**, **execution engine**, and
**frontend**. The execution engine defaults to **paper mode**, so a fresh deploy
cannot place real orders until you explicitly configure testnet/live.

> Why the per-service `railway.json` + `$PORT` Dockerfiles: Railway injects a
> `$PORT` per service and builds each service independently. The Dockerfiles now
> bind `$PORT`, and each service has a `railway.json` pinning its Dockerfile and
> health check.

## 1. Create the project and managed data stores
1. New Project → **Deploy from GitHub repo** → pick this repo.
2. Add **Database → PostgreSQL** (provides `DATABASE_URL`).
3. Add **Database → Redis** (provides `REDIS_URL`). *Optional* — only needed for
   testnet/live durability; paper mode runs without it.

## 2. Auth service
- New service → same repo → **Root Directory: `auth_service`**.
  Railway picks up `auth_service/railway.json` automatically.
- Variables:
  - `DATABASE_URL = ${{Postgres.DATABASE_URL}}`
  - `JWT_SECRET = <a long random string>`
  - `CORS_ORIGINS = https://<your-frontend-domain>`
  - `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` (creates the first admin)
- Generate a public domain (Settings → Networking → Generate Domain).

## 3. Execution engine
- New service → same repo → **Root Directory: `/`** (repo root — its Dockerfile
  copies the shared `libraries/` folder, which lives at the root).
- **Railway Config File: `execution_engine/railway.json`** (Settings → Config-as-code).
- Variables:
  - `EXECUTION_MODE = paper` &nbsp;*(leave as paper until you have tested on testnet)*
  - `REDIS_URL = ${{Redis.REDIS_URL}}` *(optional; enables durable kill-switch /
    risk state / idempotency across replicas)*
  - For testnet later: `EXECUTION_MODE=testnet`, `BINANCE_API_KEY`,
    `BINANCE_API_SECRET` (or `SECRETS_BACKEND=gcp` if you wire Secret Manager).
- Generate a public domain.

## 4. Frontend
- New service → same repo → **Root Directory: `frontend`**.
- The frontend bakes API URLs at **build time**, so set these as
  **build-time variables** (Railway: Variables, they're available to the
  Dockerfile `ARG`s):
  - `NEXT_PUBLIC_AUTH_URL = https://<auth-service-domain>`
  - `NEXT_PUBLIC_EXEC_URL = https://<execution-engine-domain>`
- Generate a public domain. Put that domain back into the auth service's
  `CORS_ORIGINS`.

## 5. Verify
- Auth: `https://<auth-domain>/health` → `{"status":"ok"}`
- Execution: `https://<exec-domain>/health` → `{"status":"ok","mode":"paper"}`
- Frontend: open the domain, sign in as the bootstrap admin, confirm the
  dashboard and the **Admin** link work.

## Notes
- **Redis is optional in paper mode.** All three Redis-backed components
  (kill-switch, risk state, idempotency) degrade to in-memory if `REDIS_URL` is
  unset. For multi-replica or testnet/live, add the Redis plugin and set
  `REDIS_URL` so that state is shared and durable.
- **SQLite vs Postgres for auth.** Without `DATABASE_URL` the auth service uses a
  local SQLite file, which resets on every redeploy on Railway's ephemeral disk.
  Always point it at the Postgres plugin in production.
- **Going live is still gated.** `EXECUTION_MODE=live` additionally requires real
  credentials and `I_UNDERSTAND_LIVE_TRADING=true`; see `docs/COMPLETION_STATUS.md`
  for what should be finished first.
