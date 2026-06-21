// frontend/src/app/dashboard/page.tsx
"use client";
import Link from "next/link";
import withAuth from "@/components/withAuth";
import { useAuth } from "@/contexts/AuthContext";
import PositionsPanel from "@/components/PositionsPanel";
import OrderTicket from "@/components/OrderTicket";
import KillSwitchControl from "@/components/KillSwitchControl";

function Dashboard() {
  const { user, logout } = useAuth();
  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <h1 className="text-2xl font-bold">Trading Dashboard</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-400">{user?.email} · {user?.role}</span>
          {user?.role === "ADMIN" && <Link href="/admin" className="text-blue-400 hover:underline">Admin</Link>}
          <button onClick={logout} className="px-3 py-1 bg-gray-700 rounded hover:bg-gray-600">Logout</button>
        </div>
      </header>
      <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2"><PositionsPanel /></div>
        <div className="space-y-6">
          <OrderTicket />
          <KillSwitchControl />
        </div>
      </div>
    </main>
  );
}

export default withAuth(Dashboard);
