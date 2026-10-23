import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Users,
  UserCheck,
  UserPlus,
  RefreshCw,
  Search,
  Filter,
  KeyRound,
  Edit2,
  Trash2,
  Shield,
  User,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/features/auth";
import {
  usersApi,
  CreateUserModal,
  EditUserModal,
  ResetPasswordModal,
  DeleteUserModal,
  type UserItem,
  type CreateUserPayload,
  type UpdateUserPayload,
  type AdminResetPasswordPayload,
} from "../index";

export function PenggunaPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Modal states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserItem | null>(null);
  const [resettingUser, setResettingUser] = useState<UserItem | null>(null);
  const [deletingUser, setDeletingUser] = useState<UserItem | null>(null);

  const fetchUsers = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);
    try {
      const data = await usersApi.getUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memuat data pengguna";
      setError(msg);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // KPI Calculations
  const totalCount = users.length;
  const activeCount = useMemo(() => users.filter((u) => u.is_active).length, [users]);
  const adminCount = useMemo(() => users.filter((u) => u.role === "admin").length, [users]);
  const activeAdminCount = useMemo(
    () => users.filter((u) => u.role === "admin" && u.is_active).length,
    [users]
  );
  const operatorCount = useMemo(() => users.filter((u) => u.role === "operator").length, [users]);

  // Filtered users
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const matchSearch = u.username.toLowerCase().includes(searchQuery.toLowerCase().trim());
      const matchRole = roleFilter === "all" || u.role.toLowerCase() === roleFilter.toLowerCase();
      const matchStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && u.is_active) ||
        (statusFilter === "inactive" && !u.is_active);
      return matchSearch && matchRole && matchStatus;
    });
  }, [users, searchQuery, roleFilter, statusFilter]);

  // Modal actions
  const handleCreateSubmit = async (payload: CreateUserPayload) => {
    await usersApi.createUser(payload);
    await fetchUsers();
  };

  const handleEditSubmit = async (userId: number, payload: UpdateUserPayload) => {
    await usersApi.updateUser(userId, payload);
    await fetchUsers();
  };

  const handleResetSubmit = async (userId: number, payload: AdminResetPasswordPayload) => {
    await usersApi.resetPassword(userId, payload);
  };

  const handleDeleteConfirm = async (userId: number) => {
    await usersApi.deleteUser(userId);
    await fetchUsers();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Manajemen Pengguna"
        description="Kelola akun pengguna, peran otorisasi, status aktivasi, dan reset kredensial sistem"
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchUsers(true)}
          disabled={isLoading || isRefreshing}
          className="flex items-center gap-1.5 cursor-pointer"
        >
          <RefreshCw className={cn("w-4 h-4", (isLoading || isRefreshing) && "animate-spin")} />
          <span>Segarkan</span>
        </Button>
        <Button
          size="sm"
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-1.5 cursor-pointer"
        >
          <UserPlus className="w-4 h-4" />
          <span>Tambah Pengguna</span>
        </Button>
      </PageHeader>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Pengguna
            </CardTitle>
            <div className="p-2 bg-slate-100 rounded-lg text-slate-600">
              <Users className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{totalCount}</div>
            <p className="text-xs text-slate-500 mt-1">Terdaftar di sistem</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Pengguna Aktif
            </CardTitle>
            <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
              <UserCheck className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">{activeCount}</div>
            <p className="text-xs text-slate-500 mt-1">Dapat melakukan login</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Administrator
            </CardTitle>
            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
              <Shield className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-indigo-600">{adminCount}</div>
            <p className="text-xs text-slate-500 mt-1">Akses konfigurasi penuh</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Operator
            </CardTitle>
            <div className="p-2 bg-amber-50 rounded-lg text-amber-600">
              <User className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">{operatorCount}</div>
            <p className="text-xs text-slate-500 mt-1">Operasional lini dan video</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Table Card */}
      <Card>
        <CardHeader className="border-b border-slate-100">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-500" />
              <CardTitle className="text-base font-semibold text-slate-900">
                Daftar Pengguna ({filteredUsers.length})
              </CardTitle>
            </div>

            {/* Filter controls */}
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="relative min-w-[200px]">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  type="text"
                  placeholder="Cari username..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 h-9 text-xs"
                />
              </div>

              <Select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="h-9 text-xs min-w-[120px]"
              >
                <option value="all">Semua Peran</option>
                <option value="admin">Admin</option>
                <option value="operator">Operator</option>
              </Select>

              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-9 text-xs min-w-[120px]"
              >
                <option value="all">Semua Status</option>
                <option value="active">Aktif</option>
                <option value="inactive">Nonaktif</option>
              </Select>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {error && (
            <div className="p-4 bg-rose-50 border-b border-rose-100 flex items-center gap-3 text-rose-700 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <div className="flex-1">
                <p className="font-semibold">Gagal memuat pengguna</p>
                <p className="text-xs text-rose-600 mt-0.5">{error}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => fetchUsers(true)}>
                Coba Lagi
              </Button>
            </div>
          )}

          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <RefreshCw className="w-6 h-6 animate-spin text-emerald-600 mb-2" />
              <p className="text-xs">Memuat daftar pengguna...</p>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="text-center py-16 text-slate-500">
              <Users className="w-10 h-10 mx-auto text-slate-300 mb-2" />
              <p className="text-sm font-medium">Tidak ada data pengguna yang cocok</p>
              <p className="text-xs text-slate-400 mt-1">Coba sesuaikan kata kunci atau filter pencarian</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50/75 border-b border-slate-100 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-6">ID</th>
                    <th className="py-3 px-6">Nama Pengguna</th>
                    <th className="py-3 px-6">Peran</th>
                    <th className="py-3 px-6">Status</th>
                    <th className="py-3 px-6 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredUsers.map((u) => {
                    const isSelf = u.id === currentUser?.id;
                    const isLastAdmin = u.role === "admin" && u.is_active && activeAdminCount <= 1;

                    return (
                      <tr key={u.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-4 px-6 font-mono text-xs text-slate-500">#{u.id}</td>
                        <td className="py-4 px-6">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900">{u.username}</span>
                            {isSelf && (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                                Akun Anda
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-4 px-6">
                          {u.role === "admin" ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                              <Shield className="w-3 h-3" />
                              Admin
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                              <User className="w-3 h-3" />
                              Operator
                            </span>
                          )}
                        </td>
                        <td className="py-4 px-6">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                              Aktif
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                              Nonaktif
                            </span>
                          )}
                        </td>
                        <td className="py-4 px-6 text-right">
                          <div className="inline-flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => setEditingUser(u)}
                              title="Ubah peran dan status"
                              aria-label="Ubah peran dan status"
                              className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setResettingUser(u)}
                              title="Reset password"
                              aria-label="Reset password"
                              className="p-1.5 text-slate-500 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors cursor-pointer"
                            >
                              <KeyRound className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeletingUser(u)}
                              disabled={isSelf || isLastAdmin}
                              title={
                                isSelf
                                  ? "Anda tidak dapat menghapus akun sendiri"
                                  : isLastAdmin
                                  ? "Tidak dapat menghapus satu-satunya admin aktif"
                                  : "Hapus akun pengguna"
                              }
                              aria-label={
                                isSelf
                                  ? "Anda tidak dapat menghapus akun sendiri"
                                  : isLastAdmin
                                  ? "Tidak dapat menghapus satu-satunya admin aktif"
                                  : "Hapus akun pengguna"
                              }
                              className={cn(
                                "p-1.5 rounded-lg transition-colors",
                                isSelf || isLastAdmin
                                  ? "text-slate-300 cursor-not-allowed opacity-50"
                                  : "text-slate-500 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                              )}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modals */}
      <CreateUserModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreateSubmit}
      />
      <EditUserModal
        isOpen={!!editingUser}
        onClose={() => setEditingUser(null)}
        user={editingUser}
        currentUserId={currentUser?.id}
        activeAdminCount={activeAdminCount}
        onSubmit={handleEditSubmit}
      />
      <ResetPasswordModal
        isOpen={!!resettingUser}
        onClose={() => setResettingUser(null)}
        user={resettingUser}
        onSubmit={handleResetSubmit}
      />
      <DeleteUserModal
        isOpen={!!deletingUser}
        onClose={() => setDeletingUser(null)}
        user={deletingUser}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}

export default PenggunaPage;
