import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { LoginForm } from "../components/LoginForm";
import { useAuth } from "../context/useAuth";

export default function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname?: string; search?: string } })?.from;
  const destination = from ? `${from.pathname || "/"}${from.search || ""}` : "/";

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate(destination, { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate, destination]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Decorative ambient background accents */}
      <div
        data-testid="ambient-glow-emerald"
        className="absolute top-1/4 -left-32 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"
      />
      <div
        data-testid="ambient-glow-indigo"
        className="absolute bottom-1/4 -right-32 w-96 h-96 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none"
      />

      <LoginForm onSuccess={() => navigate(destination, { replace: true })} />

      <footer className="mt-8 text-center text-xs text-slate-400">
        &copy; {new Date().getFullYear()} Lihat.id Computer Vision Poultry Counter System
      </footer>
    </div>
  );
}
