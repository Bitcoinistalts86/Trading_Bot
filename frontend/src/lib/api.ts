// frontend/src/lib/api.ts
// Typed client for the backend services. Base URLs come from public env vars so
// the same build works in dev (localhost) and in Docker (service names).
const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL || "http://localhost:8000";
const EXEC_URL = process.env.NEXT_PUBLIC_EXEC_URL || "http://localhost:8080";

export interface Tokens { access_token: string; refresh_token: string; token_type: string; }
export interface User { id: string; email: string; role: "USER" | "ADMIN"; is_active: boolean; created_at: string; last_login_at?: string | null; }

function tokenStore() {
  return {
    get: () => (typeof window === "undefined" ? null : localStorage.getItem("access_token")),
    set: (t: Tokens) => {
      localStorage.setItem("access_token", t.access_token);
      localStorage.setItem("refresh_token", t.refresh_token);
    },
    clear: () => { localStorage.removeItem("access_token"); localStorage.removeItem("refresh_token"); },
  };
}

async function req<T>(base: string, path: string, opts: RequestInit = {}, auth = false): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(opts.headers as Record<string, string>) };
  if (auth) {
    const t = tokenStore().get();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }
  const res = await fetch(`${base}${path}`, { ...opts, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* noop */ }
    throw new Error(detail);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  tokens: tokenStore(),

  // --- auth ---
  signup: (email: string, password: string) =>
    req<Tokens>(AUTH_URL, "/signup", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    req<Tokens>(AUTH_URL, "/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => req<User>(AUTH_URL, "/me", {}, true),

  // --- admin ---
  listUsers: () => req<User[]>(AUTH_URL, "/admin/users", {}, true),
  setRole: (id: string, role: "USER" | "ADMIN") =>
    req<User>(AUTH_URL, `/admin/users/${id}/role`, { method: "POST", body: JSON.stringify({ role }) }, true),
  setActive: (id: string, active: boolean) =>
    req<User>(AUTH_URL, `/admin/users/${id}/${active ? "enable" : "disable"}`, { method: "POST" }, true),

  // --- execution engine ---
  positions: () => req<{ mode: string; balances: Record<string, number>; risk: Record<string, unknown> }>(EXEC_URL, "/v1/positions", {}, true),
  submitOrder: (instrument: string, side: "BUY" | "SELL", quantity: number, order_type = "MARKET") =>
    req<{ status: string; client_order_id: string; mode: string }>(EXEC_URL, "/v1/order",
      { method: "POST", body: JSON.stringify({ instrument, side, quantity, order_type }) }, true),
  setKillSwitch: (level: "OFF" | "SOFT" | "HARD") =>
    req<{ status: string; level: string }>(EXEC_URL, `/v1/kill-switch?level=${level}`, { method: "POST" }, true),
  riskConfig: () => req<{ mode: string; limits: Record<string, number> }>(EXEC_URL, "/v1/risk-config", {}, true),
};
