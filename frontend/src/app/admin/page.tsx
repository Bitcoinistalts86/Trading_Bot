// frontend/src/app/admin/page.tsx
"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import withAuth from "@/components/withAuth";
import { api, User } from "@/lib/api";

function AdminPanel() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");

  const load = () => api.listUsers().then(setUsers).catch((e) => setError(e instanceof Error ? e.message : "failed"));
  useEffect(() => { load(); }, []);

  const toggleRole = async (u: User) => {
    await api.setRole(u.id, u.role === "ADMIN" ? "USER" : "ADMIN");
    load();
  };
  const toggleActive = async (u: User) => { await api.setActive(u.id, !u.is_active); load(); };

  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <h1 className="text-2xl font-bold">User Administration</h1>
        <Link href="/dashboard" className="text-blue-400 hover:underline text-sm">← Dashboard</Link>
      </header>
      <div className="p-6">
        {error && <p className="text-red-400 mb-4">{error}</p>}
        <table className="w-full text-sm bg-gray-800 rounded-lg overflow-hidden">
          <thead className="bg-gray-700 text-left text-gray-300">
            <tr><th className="p-3">Email</th><th className="p-3">Role</th><th className="p-3">Active</th><th className="p-3">Actions</th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-gray-700">
                <td className="p-3">{u.email}</td>
                <td className="p-3">{u.role}</td>
                <td className="p-3">{u.is_active ? "Yes" : "No"}</td>
                <td className="p-3 flex gap-2">
                  <button onClick={() => toggleRole(u)} className="px-2 py-1 bg-blue-600 rounded hover:bg-blue-700">
                    {u.role === "ADMIN" ? "Demote" : "Promote"}
                  </button>
                  <button onClick={() => toggleActive(u)} className={`px-2 py-1 rounded ${u.is_active ? "bg-red-600 hover:bg-red-700" : "bg-green-600 hover:bg-green-700"}`}>
                    {u.is_active ? "Disable" : "Enable"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}

export default withAuth(AdminPanel, { role: "ADMIN" });
