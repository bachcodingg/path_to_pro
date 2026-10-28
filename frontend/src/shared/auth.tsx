import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  // A second step (authenticator code) comes back as { mfaToken } instead of the user
  login: (email: string, password: string) => Promise<User | { mfaToken: string }>;
  finishMfa: (mfaToken: string, code: string) => Promise<User>;
  adopt: (token: string, user: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<{ token: string; user: User } | { mfa_required: true; mfa_token: string }>("/api/auth/login", {
      method: "POST",
      json: { email, password },
    });
    if ("mfa_token" in res) return { mfaToken: res.mfa_token };
    setToken(res.token);
    setUser(res.user);
    return res.user;
  }, []);

  const finishMfa = useCallback(async (mfaToken: string, code: string) => {
    const res = await api<{ token: string; user: User }>("/api/auth/login/mfa", { method: "POST", json: { mfa_token: mfaToken, code } });
    setToken(res.token);
    setUser(res.user);
    return res.user;
  }, []);

  const adopt = useCallback((token: string, u: User) => {
    setToken(token);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, login, finishMfa, adopt, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

export function homeFor(role: User["role"]): string {
  return { player: "/player", coach: "/coach", physio: "/physio", guardian: "/guardian", admin: "/admin" }[role];
}
