// frontend/src/app/terminal/page.tsx
"use client";
import FeaturePanel from '@/components/FeaturePanel';
import OrderTicket from '@/components/OrderTicket';
import KillSwitchControl from '@/components/KillSwitchControl';
import withAuth from '@/components/withAuth';

function TerminalPage() {
    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-gray-900 text-white">
            <h1 className="text-4xl font-bold mb-8">AI Trading Terminal</h1>
            <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="md:col-span-2">
                    <FeaturePanel />
                </div>
                <div>
                    <OrderTicket />
                    <KillSwitchControl />
                </div>
            </div>
        </main>
    );
}

export default withAuth(TerminalPage);
