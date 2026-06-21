// frontend/src/app/signup/page.tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { signup } = useAuth();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try { await signup(email, password); }
    catch (err) { setError(err instanceof Error ? err.message : "Signup failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-900">
      <div className="w-full max-w-md p-8 space-y-6 bg-gray-800 rounded-lg shadow-md">
        <h1 className="text-2xl font-bold text-center text-white">Create account</h1>
        {error && <p className="text-sm text-red-400 text-center">{error}</p>}
        <form onSubmit={onSubmit} className="space-y-5">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" required
            className="w-full px-3 py-2 text-gray-200 bg-gray-700 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 outline-none" />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password (min 8 chars)" minLength={8} required
            className="w-full px-3 py-2 text-gray-200 bg-gray-700 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 outline-none" />
          <button type="submit" disabled={busy}
            className="w-full px-4 py-2 font-semibold text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50">
            {busy ? "Creating…" : "Sign up"}
          </button>
        </form>
        <p className="text-sm text-center text-gray-400">
          Have an account? <Link href="/login" className="text-blue-400 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
