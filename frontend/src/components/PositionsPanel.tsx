// frontend/src/components/PositionsPanel.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function PositionsPanel() {
  const [data, setData] = useState<{ mode: string; balances: Record<string, number>; risk: Record<string, unknown> } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () => api.positions().then(setData).catch((e) => setError(e instanceof Error ? e.message : "failed"));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  if (error) return <div className="bg-gray-800 p-4 rounded-lg text-red-400">Execution engine: {error}</div>;
  if (!data) return <div className="bg-gray-800 p-4 rounded-lg text-gray-400">Loading positions…</div>;

  return (
    <div className="bg-gray-800 p-4 rounded-lg shadow-lg">
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-xl font-bold text-white">Account</h2>
        <span className="text-xs px-2 py-1 rounded bg-gray-700 text-gray-300 uppercase">{data.mode} mode</span>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-gray-400 text-left"><th className="pb-2">Asset</th><th className="pb-2 text-right">Balance</th></tr></thead>
        <tbody>
          {Object.entries(data.balances).length === 0 && (
            <tr><td colSpan={2} className="text-gray-500 py-2">No balances</td></tr>
          )}
          {Object.entries(data.balances).map(([asset, amt]) => (
            <tr key={asset} className="border-t border-gray-700">
              <td className="py-2 text-gray-200">{asset}</td>
              <td className="py-2 text-right text-gray-200">{Number(amt).toLocaleString(undefined, { maximumFractionDigits: 8 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <pre className="mt-3 text-xs text-gray-500 overflow-x-auto">{JSON.stringify(data.risk, null, 2)}</pre>
    </div>
  );
}
