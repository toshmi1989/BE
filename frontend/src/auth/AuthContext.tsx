import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearAuthToken,
  getAuthToken,
  getMe,
  getVersion,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  setAuthToken,
  type AuthUser,
  type VersionInfo,
} from "../api/client";

type AuthContextValue = {
  loading: boolean;
  authRequired: boolean;
  version: VersionInfo | null;
  user: AuthUser | null;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    display_name: string;
    organization_name: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authRequired, setAuthRequired] = useState(false);
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshMe = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setUser(null);
      return;
    }
    try {
      const me = await getMe();
      setUser(me);
      setError(null);
    } catch {
      clearAuthToken();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      // hydrate token from sessionStorage into memory
      const existing = getAuthToken();
      if (existing) setAuthToken(existing);
      try {
        const ver = await getVersion();
        if (cancelled) return;
        setVersion(ver);
        setAuthRequired(Boolean(ver.auth_required));
        if (getAuthToken()) {
          await refreshMe();
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          // If version endpoint fails, keep anonymous local-dev behavior
          setAuthRequired(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshMe]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const res = await apiLogin({ email, password });
    setUser({
      user_id: res.user_id,
      email: res.email,
      display_name: res.display_name,
      organization_id: res.organization_id,
      role: res.role,
    });
  }, []);

  const register = useCallback(
    async (input: {
      email: string;
      password: string;
      display_name: string;
      organization_name: string;
    }) => {
      setError(null);
      const res = await apiRegister(input);
      if (!res.access_token) {
        // register without org token — fall through to login
        await apiLogin({ email: input.email, password: input.password });
      }
      const me = await getMe().catch(() => null);
      if (me) setUser(me);
      else {
        setUser({
          user_id: res.user_id,
          email: res.email,
          display_name: res.display_name,
          organization_id: res.organization_id,
          role: res.role,
        });
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      authRequired,
      version,
      user,
      error,
      login,
      register,
      logout,
      refreshMe,
    }),
    [loading, authRequired, version, user, error, login, register, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
