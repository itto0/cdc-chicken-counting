import { useState, useEffect, type FormEvent } from "react";
import { X, UserCog, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type { UserItem, UpdateUserPayload } from "../types";

export interface EditUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserItem | null;
  currentUserId: number | undefined;
  activeAdminCount: number;
  onSubmit: (userId: number, payload: UpdateUserPayload) => Promise<void>;
}

export function EditUserModal({
  isOpen,
  onClose,
  user,
  currentUserId,
  activeAdminCount,
  onSubmit,
}: EditUserModalProps) {
  const [role, setRole] = useState<"admin" | "operator">("operator");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (user && isOpen) {
      setRole(user.role);
      setIsActive(user.is_active);
      setErrorMsg(null);
      setIsSubmitting(false);
    }
  }, [user, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSubmitting, onClose]);

  if (!isOpen || !user) return null;

  const isSelf = user.id === currentUserId;
  const isLastActiveAdmin = user.role === "admin" && user.is_active && activeAdminCount <= 1;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isSelf && !isActive) {
      setErrorMsg("You cannot deactivate your own account");
      return;
    }
    if (isLastActiveAdmin && (role !== "admin" || !isActive)) {
      setErrorMsg("Cannot change role or deactivate the only active admin");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await onSubmit(user.id, { role, is_active: isActive });
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update user";
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-user-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-100 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
              <UserCog className="w-5 h-5" />
            </div>
            <h2 id="edit-user-modal-title" className="text-lg font-semibold text-slate-900">Edit User</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-rose-700 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm flex items-center justify-between">
            <div>
              <span className="text-slate-500 font-medium">Username: </span>
              <span className="font-semibold text-slate-900">{user.username}</span>
            </div>
            <span className="text-xs text-slate-400">(cannot be changed)</span>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Role
            </label>
            <Select
              value={role}
              onChange={(e) => setRole(e.target.value as "admin" | "operator")}
              disabled={isSubmitting || isLastActiveAdmin}
            >
              <option value="operator">Operator (Monitoring & Operations)</option>
              <option value="admin">Admin (Full System Access)</option>
            </Select>
            {isLastActiveAdmin && (
              <p className="text-xs text-amber-600 mt-1">
                Role cannot be demoted because this is the only active admin.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Account Status
            </label>
            <div className="flex items-center gap-3 pt-1">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  disabled={isSubmitting || isSelf || isLastActiveAdmin}
                  className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500 disabled:opacity-50"
                />
                <span className="text-sm font-medium text-slate-700">Active Account</span>
              </label>
            </div>
            {isSelf && (
              <p className="text-xs text-amber-600 mt-1">
                You cannot deactivate the account currently in use.
              </p>
            )}
            {!isSelf && isLastActiveAdmin && (
              <p className="text-xs text-amber-600 mt-1">
                This account cannot be deactivated because it is the only active admin.
              </p>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
