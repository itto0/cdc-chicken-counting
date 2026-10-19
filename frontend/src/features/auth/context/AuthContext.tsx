import { createContext, useCallback, useEffect, useState, type ReactNode } from "react";
import { getAuthToken, setAuthToken } from "@/lib/http";
import { authApi } from "../api/auth.api";
import type { AuthContextType, LoginCredentials, User } from "../types";

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(() => getAuthToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    setAuthToken(null);
    setTokenState(null);
    setUser(null);
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const res = await authApi.login(credentials);
    setAuthToken(res.access_token);
    setTokenState(res.access_token);
    setUser(res.user);
  }, []);

  useEffect(() => {
    let isMounted = true;
    const initialToken = getAuthToken();

    if (!initialToken) {
      setIsLoading(false);
      return;
    }

    authApi
      .getMe()
      .then((userData) => {
        if (isMounted) {
          setUser(userData);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          logout();
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [logout]);

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("auth:unauthorized", handleUnauthorized);
    };
  }, [logout]);

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
