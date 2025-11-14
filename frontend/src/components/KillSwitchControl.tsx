// frontend/src/components/KillSwitchControl.tsx
"use client";

import { useState, useEffect } from 'react';

export default function KillSwitchControl() {
    const [isActive, setIsActive] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    const fetchStatus = async () => {
        try {
            // Placeholder for real API call with auth
            const response = await fetch('/api/killswitch');
            if (response.ok) {
                const data = await response.json();
                setIsActive(data.killswitch_active);
            }
        } catch (error) {
            console.error('Failed to fetch kill-switch status:', error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchStatus();
    }, []);

    const handleToggle = async () => {
        setIsLoading(true);
        try {
            // Placeholder for real API call with auth
            await fetch('/api/killswitch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active: !isActive }),
            });
            setIsActive(!isActive);
        } catch (error) {
            console.error('Failed to toggle kill-switch:', error);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow-lg mt-4">
            <h2 className="text-xl font-bold mb-4 text-white">Global Kill-Switch</h2>
            <div className="flex items-center justify-between">
                <span className={`text-lg font-bold ${isActive ? 'text-red-500' : 'text-green-500'}`}>
                    {isLoading ? 'Loading...' : (isActive ? 'ACTIVE' : 'INACTIVE')}
                </span>
                <button
                    onClick={handleToggle}
                    disabled={isLoading}
                    className={`px-4 py-2 rounded-md text-white font-bold ${
                        isActive
                            ? 'bg-green-600 hover:bg-green-700'
                            : 'bg-red-600 hover:bg-red-700'
                    }`}
                >
                    {isActive ? 'Deactivate' : 'Activate'}
                </button>
            </div>
        </div>
    );
}
