import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, clearAuth, getStoredUser, getToken, setStoredUser, setToken } from "./api";
import type { Role, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<User>;
  register: (payload: {
    username: string;
    password: string;
    role: Role;
    display_name: string;
    company_name?: string;
  }) => Promise<User>;
  refreshUser: () => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => getStoredUser<User>());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get<User>("/auth/me")
      .then((me) => {
        setUser(me);
        setStoredUser(me);
      })
      .catch(() => {
        clearAuth();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener("jc:unauthorized", onUnauthorized);
    return () => window.removeEventListener("jc:unauthorized", onUnauthorized);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api.post<{ access_token: string; user: User }>("/auth/login", {
      username,
      password,
    });
    setToken(data.access_token);
    setStoredUser(data.user);
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(
    async (payload: {
      username: string;
      password: string;
      role: Role;
      display_name: string;
      company_name?: string;
    }) => {
      const data = await api.post<{ access_token: string; user: User }>("/auth/register", payload);
      setToken(data.access_token);
      setStoredUser(data.user);
      setUser(data.user);
      return data.user;
    },
    [],
  );

  const refreshUser = useCallback(async () => {
    const me = await api.get<User>("/auth/me");
    setUser(me);
    setStoredUser(me);
    return me;
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, refreshUser, logout }),
    [user, loading, login, register, refreshUser, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}

export function homePath(role?: Role | null) {
  return role === "employer" ? "/employer/jobs" : "/seeker/jobs";
}

export function ProtectedRoute({ role, children }: { role: Role; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-primary" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (user.role !== role) {
    return <Navigate to={homePath(user.role)} replace />;
  }
  return <>{children}</>;
}
