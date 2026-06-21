// frontend/src/contexts/AuthContext.tsx
"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, User } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Hydrate the session on load: if we have a token, fetch the profile.
  useEffect(() => {
    (async () => {
      if (api.tokens.get()) {
        try { setUser(await api.me()); } catch { api.tokens.clear(); }
      }
      setLoading(false);
    })();
  }, []);

  const afterAuth = async () => {
    setUser(await api.me());
    router.push("/dashboard");
  };

  const login = async (email: string, password: string) => {
    api.tokens.set(await api.login(email, password));
    await afterAuth();
  };

  const signup = async (email: string, password: string) => {
    api.tokens.set(await api.signup(email, password));
    await afterAuth();
  };

  const logout = () => {
    api.tokens.clear();
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
};
