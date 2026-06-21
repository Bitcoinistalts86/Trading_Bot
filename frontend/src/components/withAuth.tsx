// frontend/src/components/withAuth.tsx
// Route guard HOC. Redirects unauthenticated users to /login, and (optionally)
// enforces a required role. This component was imported by the app but never
// existed -- which broke the build. It exists now.
"use client";
import { ComponentType, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

interface Options { role?: "ADMIN" | "USER"; }

export default function withAuth<P extends object>(Wrapped: ComponentType<P>, opts: Options = {}) {
  return function Guarded(props: P) {
    const { user, loading } = useAuth();
    const router = useRouter();

    useEffect(() => {
      if (loading) return;
      if (!user) { router.replace("/login"); return; }
      if (opts.role && user.role !== opts.role) { router.replace("/dashboard"); }
    }, [user, loading, router]);

    if (loading || !user) return <div className="min-h-screen flex items-center justify-center bg-gray-900 text-gray-400">Loading…</div>;
    if (opts.role && user.role !== opts.role) return null;
    return <Wrapped {...props} />;
  };
}
