// frontend/src/components/FeaturePanel.tsx
"use client";

import { useState, useEffect } from 'react';

interface FeatureData {
    instrument: string;
    timestamp: string;
    mid_price?: number;
    spread?: number;
    volume_1s?: number;
    volume_5s?: number;
    trade_imbalance_5s?: number;
    volatility_30s?: number;
}

export default function FeaturePanel() {
    const [features, setFeatures] = useState<FeatureData | null>(null);
    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        // Replace with your actual WebSocket URL
        const wsUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8000/ws/features';
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connected');
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setFeatures(data);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            setIsConnected(false);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        // Cleanup on component unmount
        return () => {
            ws.close();
        };
    }, []);

    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow-lg">
            <h2 className="text-xl font-bold mb-4 text-white">Real-Time Features</h2>
            <div className={`text-sm mb-2 ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
                {isConnected ? '● Connected' : '● Disconnected'}
            </div>
            {features ? (
                <div className="grid grid-cols-2 gap-4 text-gray-300">
                    <div><strong>Instrument:</strong> {features.instrument}</div>
                    <div><strong>Timestamp:</strong> {new Date(features.timestamp).toLocaleTimeString()}</div>
                    <div><strong>Mid Price:</strong> {features.mid_price?.toFixed(2)}</div>
                    <div><strong>Spread:</strong> {features.spread?.toFixed(4)}</div>
                    <div><strong>Volume (1s):</strong> {features.volume_1s?.toFixed(2)}</div>
                    <div><strong>Volume (5s):</strong> {features.volume_5s?.toFixed(2)}</div>
                    <div><strong>Imbalance (5s):</strong> {features.trade_imbalance_5s?.toFixed(2)}</div>
                    <div><strong>Volatility (30s):</strong> {features.volatility_30s?.toFixed(6)}</div>
                </div>
            ) : (
                <p className="text-gray-500">Waiting for data...</p>
            )}
        </div>
    );
}
