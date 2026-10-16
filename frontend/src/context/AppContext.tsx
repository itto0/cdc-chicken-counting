import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { LineItem, UserRole } from "../types";
import { getLines } from "../services/apiClient";

export interface AppContextType {
  currentLineId: string;
  setLineId: (lineId: string) => void;
  currentRole: UserRole;
  setRole: (role: UserRole) => void;
  lines: LineItem[];
  isConnected: boolean;
  refreshLines: () => Promise<void>;
}

export const FALLBACK_MOCK_LINE: LineItem = {
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
  const [currentLineId, setLineId] = useState<string>(initialLineId);
  const [currentRole, setRole] = useState<UserRole>(initialRole);
  const [lines, setLines] = useState<LineItem[]>([FALLBACK_MOCK_LINE]);
  const [isConnected, setIsConnected] = useState<boolean>(false);

  const refreshLines = useCallback(async () => {
    try {
      const data = await getLines();
      if (Array.isArray(data) && data.length > 0) {
        setLines(data);
        setIsConnected(true);
        // If currentLineId is not among fetched lines, select the first line
        setLineId((prev) => {
          const exists = data.some((item) => item.id === prev);
          return exists ? prev : data[0].id;
        });
      } else {
        setLines([FALLBACK_MOCK_LINE]);
        setIsConnected(false);
      }
    } catch (err) {
      // In local development or offline mode, fall back to mock line gracefully
      setLines([FALLBACK_MOCK_LINE]);
      setIsConnected(false);
    }
  }, []);

  useEffect(() => {
    refreshLines();
  }, [refreshLines]);

  const value: AppContextType = useMemo(
    () => ({
      currentLineId,
      setLineId,
      currentRole,
      setRole,
      lines,
      isConnected,
      refreshLines,
    }),
    [currentLineId, currentRole, lines, isConnected, refreshLines]
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
