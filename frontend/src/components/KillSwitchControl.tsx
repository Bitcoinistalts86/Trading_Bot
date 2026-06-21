// frontend/src/components/KillSwitchControl.tsx
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function KillSwitchControl() {
  const [level, setLevel] = useState<"OFF" | "SOFT" | "HARD">("OFF");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const set = async (next: "OFF" | "SOFT" | "HARD") => {
    setBusy(true); setMsg("");
    try { await api.setKillSwitch(next); setLevel(next); }
    catch (err) { setMsg(err instanceof Error ? err.message : "failed"); }
    finally { setBusy(false); }
  };

  const colour = level === "OFF" ? "text-green-500" : level === "SOFT" ? "text-yellow-400" : "text-red-500";

  return (
    <div className="bg-gray-800 p-4 rounded-lg shadow-lg">
      <h2 className="text-xl font-bold mb-3 text-white">Global Kill-Switch</h2>
      <p className="mb-3">Status: <span className={`font-bold ${colour}`}>{level}</span></p>
      <div className="flex gap-2">
        {(["OFF", "SOFT", "HARD"] as const).map((l) => (
          <button key={l} disabled={busy} onClick={() => set(l)}
            className={`flex-1 py-2 rounded-md text-white font-bold disabled:opacity-50 ${
              l === "OFF" ? "bg-green-600 hover:bg-green-700" : l === "SOFT" ? "bg-yellow-600 hover:bg-yellow-700" : "bg-red-600 hover:bg-red-700"}`}>
            {l}
          </button>
        ))}
      </div>
      {msg && <p className="text-sm mt-3 text-red-400">{msg}</p>}
    </div>
  );
}
