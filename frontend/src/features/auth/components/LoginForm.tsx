import { useState, type FormEvent } from "react";
import { Lock, User, AlertCircle, Loader2, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../context/useAuth";

interface LoginFormProps {
  onSuccess?: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Silakan isi nama pengguna dan kata sandi.");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await login({ username: username.trim(), password });
      onSuccess?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Gagal masuk ke sistem";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError(null);
  };

  return (
    <div className="w-full max-w-md border border-slate-700/80 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-sm">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold  tracking-tight">Masuk</h1>
        <p className="text-sm mt-1">Poultry Counter Central Dashboard</p>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-start gap-3 text-rose-400 text-sm"
        >
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="username"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5"
          >
            Nama Pengguna
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <User className="w-4 h-4" />
            </div>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin / operator"
              required
              autoFocus
              className="w-full pl-10 pr-4 py-2.5 border border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5"
          >
            Kata Sandi
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Lock className="w-4 h-4" />
            </div>
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full pl-10 pr-10 py-2.5 border border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-700 hover:text-slate-900"
              tabIndex={-1}
              aria-label={showPassword ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50  rounded-xl text-sm font-semibold shadow-lg shadow-emerald-900/30 flex items-center justify-center gap-2 transition-all cursor-pointer"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Memverifikasi...</span>
            </>
          ) : (
            <span>Masuk</span>
          )}
        </button>
      </form>

      {/* Demo Credentials Quick-Fill helper */}
      {import.meta.env.DEV && (
        <div className="mt-6 pt-5 border-t border-slate-700/60">
          <p className="text-xs text-slate-400 text-center mb-2.5">Pilih akun demonstrasi:</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleQuickFill("admin", "admin123")}
              className="py-1.5 px-3 bg-slate-700/60 hover:bg-slate-700 border border-slate-600/50 rounded-lg text-xs font-medium text-slate-200 transition-colors"
            >
              Admin (admin123)
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill("operator", "operator123")}
              className="py-1.5 px-3 bg-slate-700/60 hover:bg-slate-700 border border-slate-600/50 rounded-lg text-xs font-medium text-slate-200 transition-colors"
            >
              Operator (operator123)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
