// frontend/src/components/OrderTicket.tsx
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function OrderTicket() {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [instrument, setInstrument] = useState("BTCUSDT");
  const [quantity, setQuantity] = useState("");
  const [status, setStatus] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("Submitting…");
    try {
      const res = await api.submitOrder(instrument, side, parseFloat(quantity));
      setStatus(`Accepted (${res.mode}) — id ${res.client_order_id}`);
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : "failed"}`);
    }
  };

  return (
    <form onSubmit={onSubmit} className="bg-gray-800 p-4 rounded-lg shadow-lg">
      <h2 className="text-xl font-bold mb-4 text-white">Place Order</h2>
      <div className="flex mb-4">
        <button type="button" onClick={() => setSide("BUY")}
          className={`flex-1 p-2 rounded-l-md ${side === "BUY" ? "bg-green-600" : "bg-gray-700"} text-white`}>BUY</button>
        <button type="button" onClick={() => setSide("SELL")}
          className={`flex-1 p-2 rounded-r-md ${side === "SELL" ? "bg-red-600" : "bg-gray-700"} text-white`}>SELL</button>
      </div>
      <label className="block text-sm text-gray-300">Instrument</label>
      <input value={instrument} onChange={(e) => setInstrument(e.target.value.toUpperCase())}
        className="mt-1 mb-4 block w-full bg-gray-900 border border-gray-700 rounded-md text-white px-2 py-1" />
      <label className="block text-sm text-gray-300">Quantity</label>
      <input type="number" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="0.00"
        className="mt-1 mb-4 block w-full bg-gray-900 border border-gray-700 rounded-md text-white px-2 py-1" />
      <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded">Submit Order</button>
      {status && <p className="text-sm mt-3 text-gray-400">{status}</p>}
    </form>
  );
}
