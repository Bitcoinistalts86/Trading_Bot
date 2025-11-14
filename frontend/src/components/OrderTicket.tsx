// frontend/src/components/OrderTicket.tsx
"use client";

import { useState } from 'react';

export default function OrderTicket() {
    const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
    const [quantity, setQuantity] = useState('');
    const [status, setStatus] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatus('Submitting...');

        try {
            // This is a placeholder. You'll need to implement a real API client
            // and handle authentication (e.g., sending a JWT token).
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    instrument: 'BTCUSDT', // Placeholder
                    side,
                    quantity: parseFloat(quantity),
                }),
            });

            if (!response.ok) {
                throw new Error(`Failed to place order: ${response.statusText}`);
            }

            const result = await response.json();
            setStatus(`Order submitted successfully! ID: ${result.trade_id}`);
        } catch (error) {
            setStatus(`Error: ${error.message}`);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="bg-gray-800 p-4 rounded-lg shadow-lg mt-4">
            <h2 className="text-xl font-bold mb-4 text-white">Place Order</h2>
            <div className="flex mb-4">
                <button
                    type="button"
                    onClick={() => setSide('BUY')}
                    className={`flex-1 p-2 rounded-l-md ${side === 'BUY' ? 'bg-green-600' : 'bg-gray-700'} text-white`}
                >
                    BUY
                </button>
                <button
                    type="button"
                    onClick={() => setSide('SELL')}
                    className={`flex-1 p-2 rounded-r-md ${side === 'SELL' ? 'bg-red-600' : 'bg-gray-700'} text-white`}
                >
                    SELL
                </button>
            </div>
            <div className="mb-4">
                <label className="block text-sm font-medium text-gray-300">Quantity</label>
                <input
                    type="number"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    placeholder="0.00"
                    className="mt-1 block w-full bg-gray-900 border-gray-700 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 text-white"
                />
            </div>
            <button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded"
            >
                Submit Order
            </button>
            {status && <p className="text-sm mt-4 text-gray-400">{status}</p>}
        </form>
    );
}
