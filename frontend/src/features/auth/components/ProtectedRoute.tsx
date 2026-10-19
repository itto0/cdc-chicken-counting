import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "../context/useAuth";

interface ProtectedRouteProps {
  children?: ReactNode;
  allowedRoles?: string[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        role="status"
        aria-label="Memverifikasi autentikasi..."
        className="flex items-center justify-center min-h-[350px]"
      >
        <div className="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && user) {
    const userRole = (user.role || "").toLowerCase();
    const hasRole = allowedRoles.some((r) => r.toLowerCase() === userRole);
    if (!hasRole) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-6 text-center">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/10 text-amber-500 flex items-center justify-center mb-4">
            <ShieldAlert className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Akses Ditolak</h2>
          <p className="text-sm text-slate-500 max-w-md mb-6">
            Akun Anda ({user.username} - {user.role}) tidak memiliki izin untuk mengakses halaman ini. Halaman ini memerlukan peran: {allowedRoles.join(", ")}.
          </p>
        </div>
      );
    }
  }

  return <>{children}</>;
}
