"use client";

import * as React from "react";
import {
  api,
  setAccessToken,
  type LoginPayload,
  type RegisterPayload,
  type User,
} from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  /** True during the initial silent-refresh bootstrap. */
  loading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  /** Adopt a session from an access token (used by the OAuth callback). */
  adoptToken: (token: string) => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [loading, setLoading] = React.useState(true);

  // On mount, try a silent refresh: if the httpOnly refresh cookie is still
  // valid we get a fresh access token and rehydrate the user — no re-login.
  React.useEffect(() => {
    let active = true;
    (async () => {
      const token = await api.auth.refresh();
      if (!active) return;
      if (token) {
        try {
          setUser(await api.auth.me());
        } catch {
          setUser(null);
        }
      }
      setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, []);

  const login = React.useCallback(async (payload: LoginPayload) => {
    const res = await api.auth.login(payload);
    setAccessToken(res.access_token);
    setUser(res.user);
  }, []);

  const register = React.useCallback(async (payload: RegisterPayload) => {
    const res = await api.auth.register(payload);
    setAccessToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = React.useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  const adoptToken = React.useCallback(async (token: string) => {
    setAccessToken(token);
    setUser(await api.auth.me());
  }, []);

  const value = React.useMemo(
    () => ({ user, loading, login, register, logout, adoptToken }),
    [user, loading, login, register, logout, adoptToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
