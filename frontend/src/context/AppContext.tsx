import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { CreateLinePayload, Line, UpdateLinePayload, UserRole } from "@/types";
import { apiClient } from "@/services/apiClient";
import { useAuth } from "@/features/auth";

export interface AppContextType {
  currentLineId: string;
  setLineId: (lineId: string) => void;
  setCurrentLineId: (lineId: string) => void;
  currentRole: UserRole;
  setRole: (role: UserRole) => void;
  lines: Line[];
  isConnected: boolean;
  refreshLines: () => Promise<void>;
  fetchLines: () => Promise<void>;
  createLine: (payload: CreateLinePayload) => Promise<Line>;
  updateLine: (lineId: string, payload: UpdateLinePayload) => Promise<Line>;
  deleteLine: (lineId: string) => Promise<Line>;
}

export const FALLBACK_MOCK_LINE: Line = {
  id: "line-1",
  name: "Conveyor Line 1",
  is_active: true,
  daily_target: 60000,
  status: "online",
  total_today: 0,
  last_ping: null,
};

export const AppContext = createContext<AppContextType | undefined>(undefined);

export interface AppProviderProps {
  children: ReactNode;
  initialLineId?: string;
  initialRole?: UserRole;
}

export const AppProvider: React.FC<AppProviderProps> = ({
  children,
  initialLineId = "line-1",
  initialRole = "ADMIN",
}) => {
  const { token } = useAuth();
  const [currentLineId, setCurrentLineId] = useState<string>(initialLineId);
  const setLineId = setCurrentLineId;
  const [currentRole, setRole] = useState<UserRole>(initialRole);
  const [lines, setLines] = useState<Line[]>([FALLBACK_MOCK_LINE]);
  const [isConnected, setIsConnected] = useState<boolean>(false);

  const fetchLines = useCallback(async () => {
    try {
      const data = await apiClient.getLines();
      if (Array.isArray(data) && data.length > 0) {
        setLines(data);
        setIsConnected(true);
        // If currentLineId is not among fetched lines, select the first line
        setCurrentLineId((prev) => {
          const exists = data.some((item) => item.id === prev);
          return exists ? prev : data[0].id;
        });
      } else {
        setLines([FALLBACK_MOCK_LINE]);
        setIsConnected(false);
      }
    } catch {
      // In local development or offline mode, fall back to mock line gracefully
      setLines([FALLBACK_MOCK_LINE]);
      setIsConnected(false);
    }
  }, []);

  const refreshLines = fetchLines;

  useEffect(() => {
    if (token) {
      fetchLines();
    } else {
      setLines([FALLBACK_MOCK_LINE]);
      setIsConnected(false);
    }
  }, [token, fetchLines]);

  const createLine = useCallback(async (payload: CreateLinePayload) => {
    const newLine = await apiClient.createLine(payload);
    await fetchLines();
    setCurrentLineId(newLine.id);
    return newLine;
  }, [fetchLines]);

  const updateLine = useCallback(async (lineId: string, payload: UpdateLinePayload) => {
    const updated = await apiClient.updateLine(lineId, payload);
    await fetchLines();
    return updated;
  }, [fetchLines]);

  const deleteLine = useCallback(async (lineId: string) => {
    const deleted = await apiClient.deleteLine(lineId);
    await fetchLines();
    return deleted;
  }, [fetchLines]);

  const value: AppContextType = useMemo(
    () => ({
      currentLineId,
      setLineId,
      setCurrentLineId,
      currentRole,
      setRole,
      lines,
      isConnected,
      refreshLines,
      fetchLines,
      createLine,
      updateLine,
      deleteLine,
    }),
    [
      currentLineId,
      setLineId,
      setCurrentLineId,
      currentRole,
      setRole,
      lines,
      isConnected,
      refreshLines,
      fetchLines,
      createLine,
      updateLine,
      deleteLine,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export function useAppContext(): AppContextType {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within an AppProvider");
  }
  return context;
}

export default AppContext;
