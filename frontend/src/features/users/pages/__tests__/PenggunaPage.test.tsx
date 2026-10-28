import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PenggunaPage } from "../PenggunaPage";
import { usersApi } from "../../api/users.api";
import type { UserItem } from "../../types";

const mockCurrentUser: {
  id: number;
  username: string;
  role: "admin" | "operator";
  is_active: boolean;
} = {
  id: 1,
  username: "admin_super",
  role: "admin",
  is_active: true,
};

let currentUserMock = { ...mockCurrentUser };

vi.mock("@/features/auth", () => ({
  useAuth: () => ({
    user: currentUserMock,
    token: "fake-token",
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

const mockUsersList: UserItem[] = [
  {
    id: 1,
    username: "admin_super",
    role: "admin",
    is_active: true,
  },
  {
    id: 2,
    username: "admin_two",
    role: "admin",
    is_active: true,
  },
  {
    id: 3,
    username: "operator_one",
    role: "operator",
    is_active: true,
  },
  {
    id: 4,
    username: "operator_two",
    role: "operator",
    is_active: false,
  },
];

describe("PenggunaPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    currentUserMock = { ...mockCurrentUser };
  });

  it("fetches and displays user list with KPI counts", async () => {
    const getUsersSpy = vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);

    render(<PenggunaPage />);

    expect(screen.getByText("Loading user list...")).toBeDefined();

    await waitFor(() => {
      expect(getUsersSpy).toHaveBeenCalledTimes(1);
    });

    // Check Page Header
    expect(screen.getByRole("heading", { name: "User Management" })).toBeDefined();
    expect(
      screen.getByText("Manage user accounts, roles, and access permissions in the system.")
    ).toBeDefined();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Add User" })).toBeDefined();

    // Check KPI Cards
    await waitFor(() => {
      expect(screen.getByText("Total Users")).toBeDefined();
      expect(screen.getByText("Registered in system")).toBeDefined();
      expect(screen.getByText("4")).toBeDefined(); // Total
      expect(screen.getByText("Active Users")).toBeDefined();
      expect(screen.getByText("Can sign in")).toBeDefined();
      expect(screen.getByText("3")).toBeDefined(); // Active
      expect(screen.getAllByText("2")).toHaveLength(2); // Administrator (2) & Operator (2)
      expect(screen.getByText("Full configuration access")).toBeDefined();
      expect(screen.getByText("Line and video operations")).toBeDefined();
    });

    // Check table headers and users rendered
    expect(screen.getByText("User List (4)")).toBeDefined();
    expect(screen.getByText("Username")).toBeDefined();
    expect(screen.getByText("Role")).toBeDefined();
    expect(screen.getByText("Status")).toBeDefined();
    expect(screen.getByText("Actions")).toBeDefined();
    expect(screen.getByText("admin_super")).toBeDefined();
    expect(screen.getByText("admin_two")).toBeDefined();
    expect(screen.getByText("operator_one")).toBeDefined();
    expect(screen.getByText("operator_two")).toBeDefined();

    // Check "Your Account" badge for current user (id: 1)
    expect(screen.getByText("Your Account")).toBeDefined();

    // Check Active and Inactive status badges
    expect(screen.getAllByText("Active").length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText("Inactive").length).toBeGreaterThanOrEqual(1);
  });

  it("filters users by search query", async () => {
    vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_super")).toBeDefined();
    });

    const searchInput = screen.getByPlaceholderText("Search username...");
    fireEvent.change(searchInput, { target: { value: "operator" } });

    expect(screen.getByText("User List (2)")).toBeDefined();
    expect(screen.getByText("operator_one")).toBeDefined();
    expect(screen.getByText("operator_two")).toBeDefined();
    expect(screen.queryByText("admin_super")).toBeNull();
    expect(screen.queryByText("admin_two")).toBeNull();

    // Search nonexistent user
    fireEvent.change(searchInput, { target: { value: "nonexistent_user" } });
    expect(screen.getByText("No matching users found")).toBeDefined();
    expect(screen.getByText("Try adjusting search keywords or filters")).toBeDefined();
  });

  it("filters users by role", async () => {
    vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_super")).toBeDefined();
    });

    const roleSelect = screen.getByDisplayValue("All Roles");

    // Filter to admin
    fireEvent.change(roleSelect, { target: { value: "admin" } });
    expect(screen.getByText("User List (2)")).toBeDefined();
    expect(screen.getByText("admin_super")).toBeDefined();
    expect(screen.getByText("admin_two")).toBeDefined();
    expect(screen.queryByText("operator_one")).toBeNull();

    // Filter to operator
    fireEvent.change(roleSelect, { target: { value: "operator" } });
    expect(screen.getByText("User List (2)")).toBeDefined();
    expect(screen.getByText("operator_one")).toBeDefined();
    expect(screen.getByText("operator_two")).toBeDefined();
    expect(screen.queryByText("admin_super")).toBeNull();
  });

  it("filters users by status", async () => {
    vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_super")).toBeDefined();
    });

    const statusSelect = screen.getByDisplayValue("All Status");

    // Filter to active
    fireEvent.change(statusSelect, { target: { value: "active" } });
    expect(screen.getByText("User List (3)")).toBeDefined();
    expect(screen.getByText("admin_super")).toBeDefined();
    expect(screen.getByText("admin_two")).toBeDefined();
    expect(screen.getByText("operator_one")).toBeDefined();
    expect(screen.queryByText("operator_two")).toBeNull();

    // Filter to inactive
    fireEvent.change(statusSelect, { target: { value: "inactive" } });
    expect(screen.getByText("User List (1)")).toBeDefined();
    expect(screen.getByText("operator_two")).toBeDefined();
    expect(screen.queryByText("admin_super")).toBeNull();
  });

  it("disables delete button for current user (Invariant 1: Admin self-deletion prevented)", async () => {
    vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_super")).toBeDefined();
    });

    const selfDeleteBtn = screen.getByTitle("You cannot delete your own account");
    expect(selfDeleteBtn).toBeDefined();
    expect(selfDeleteBtn).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("You cannot delete your own account")).toBe(selfDeleteBtn);
  });

  it("disables delete button for last active admin (Invariant 4: Last active admin deletion prevented)", async () => {
    // Current user is operator (id: 3), only 1 active admin (id: 2)
    currentUserMock = {
      id: 3,
      username: "operator_one",
      role: "operator",
      is_active: true,
    };

    const singleAdminList: UserItem[] = [
      {
        id: 2,
        username: "sole_admin",
        role: "admin",
        is_active: true,
      },
      {
        id: 3,
        username: "operator_one",
        role: "operator",
        is_active: true,
      },
    ];

    vi.spyOn(usersApi, "getUsers").mockResolvedValue(singleAdminList);
    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("sole_admin")).toBeDefined();
    });

    const lastAdminDeleteBtn = screen.getByTitle("Cannot delete the only active admin");
    expect(lastAdminDeleteBtn).toBeDefined();
    expect(lastAdminDeleteBtn).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Cannot delete the only active admin")).toBe(lastAdminDeleteBtn);
  });

  it("opens and handles CreateUserModal workflow", async () => {
    const getUsersSpy = vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    const createUserSpy = vi.spyOn(usersApi, "createUser").mockResolvedValue({
      id: 5,
      username: "new_operator",
      role: "operator",
      is_active: true,
    });

    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_super")).toBeDefined();
    });

    // Open modal
    const addBtn = screen.getByRole("button", { name: "Add User" });
    fireEvent.click(addBtn);

    expect(screen.getByText("Add New User")).toBeDefined();

    // Fill form
    fireEvent.change(screen.getByPlaceholderText("e.g. op_johndoe"), {
      target: { value: "new_operator" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimum 6 characters"), {
      target: { value: "secret123" },
    });

    // Submit
    const submitBtn = screen.getByRole("button", { name: "Save User" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(createUserSpy).toHaveBeenCalledWith({
        username: "new_operator",
        password: "secret123",
        role: "operator",
        is_active: true,
      });
      // fetchUsers re-called on success
      expect(getUsersSpy).toHaveBeenCalledTimes(2);
      expect(screen.queryByText("Add New User")).toBeNull();
    });
  });

  it("opens and handles EditUserModal workflow", async () => {
    const getUsersSpy = vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    const updateUserSpy = vi.spyOn(usersApi, "updateUser").mockResolvedValue({
      ...mockUsersList[1],
      role: "operator",
    });

    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_two")).toBeDefined();
    });

    const editButtons = screen.getAllByTitle("Edit role and status");
    // Click edit on admin_two (index 1)
    fireEvent.click(editButtons[1]);

    expect(screen.getByText("Edit User")).toBeDefined();
    expect(screen.getAllByText("admin_two").length).toBeGreaterThanOrEqual(1);

    // Save changes
    const submitBtn = screen.getByRole("button", { name: "Save Changes" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(updateUserSpy).toHaveBeenCalledWith(2, {
        role: "admin",
        is_active: true,
      });
      expect(getUsersSpy).toHaveBeenCalledTimes(2);
      expect(screen.queryByText("Edit User")).toBeNull();
    });
  });

  it("opens and handles ResetPasswordModal workflow", async () => {
    vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    const resetPasswordSpy = vi
      .spyOn(usersApi, "resetPassword")
      .mockResolvedValue({ message: "Password berhasil direset" });

    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_two")).toBeDefined();
    });

    const resetButtons = screen.getAllByTitle("Reset password");
    // Click reset password on admin_two (index 1)
    fireEvent.click(resetButtons[1]);

    expect(screen.getByText("Reset User Password")).toBeDefined();

    // Fill new password and confirm
    fireEvent.change(screen.getByPlaceholderText("Minimum 6 characters"), {
      target: { value: "newpass123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Re-enter new password"), {
      target: { value: "newpass123" },
    });

    const submitBtn = screen.getByRole("button", { name: "Reset Password" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(resetPasswordSpy).toHaveBeenCalledWith(2, {
        new_password: "newpass123",
      });
      expect(screen.queryByText("Reset User Password")).toBeNull();
    });
  });

  it("opens and handles DeleteUserModal workflow", async () => {
    const getUsersSpy = vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    const deleteUserSpy = vi
      .spyOn(usersApi, "deleteUser")
      .mockResolvedValue({ message: "Pengguna berhasil dihapus" });

    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_two")).toBeDefined();
    });

    // admin_two is deletable because activeAdminCount=2 and admin_two is not self
    const deleteButtons = screen.getAllByTitle("Delete user account");
    fireEvent.click(deleteButtons[0]); // First enabled delete button corresponds to admin_two (since admin_super is disabled)

    expect(screen.getByRole("heading", { name: "Delete User" })).toBeDefined();
    expect(screen.getByText(/Are you sure you want to delete user account/)).toBeDefined();

    const confirmBtn = screen.getByRole("button", { name: "Delete User" });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(deleteUserSpy).toHaveBeenCalledWith(2);
      expect(getUsersSpy).toHaveBeenCalledTimes(2);
      expect(screen.queryByRole("heading", { name: "Delete User" })).toBeNull();
    });
  });

  it("can cancel/close modals without triggering API mutations", async () => {
    vi.spyOn(usersApi, "getUsers").mockResolvedValue(mockUsersList);
    const createUserSpy = vi.spyOn(usersApi, "createUser");
    const updateUserSpy = vi.spyOn(usersApi, "updateUser");
    const resetPasswordSpy = vi.spyOn(usersApi, "resetPassword");
    const deleteUserSpy = vi.spyOn(usersApi, "deleteUser");

    render(<PenggunaPage />);

    await waitFor(() => {
      expect(screen.getByText("admin_super")).toBeDefined();
    });

    // 1. Open and cancel CreateUserModal
    fireEvent.click(screen.getByRole("button", { name: "Add User" }));
    expect(screen.getByText("Add New User")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Add New User")).toBeNull();
    expect(createUserSpy).not.toHaveBeenCalled();

    // 2. Open and cancel EditUserModal
    const editButtons = screen.getAllByTitle("Edit role and status");
    fireEvent.click(editButtons[1]);
    expect(screen.getByText("Edit User")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Edit User")).toBeNull();
    expect(updateUserSpy).not.toHaveBeenCalled();

    // 3. Open and cancel ResetPasswordModal
    const resetButtons = screen.getAllByTitle("Reset password");
    fireEvent.click(resetButtons[1]);
    expect(screen.getByText("Reset User Password")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Reset User Password")).toBeNull();
    expect(resetPasswordSpy).not.toHaveBeenCalled();

    // 4. Open and cancel DeleteUserModal
    const deleteButtons = screen.getAllByTitle("Delete user account");
    fireEvent.click(deleteButtons[0]);
    expect(screen.getByRole("heading", { name: "Delete User" })).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("heading", { name: "Delete User" })).toBeNull();
    expect(deleteUserSpy).not.toHaveBeenCalled();
  });

  it("handles manual refresh and error retry", async () => {
    const getUsersSpy = vi
      .spyOn(usersApi, "getUsers")
      .mockRejectedValueOnce(new Error("Koneksi terputus"))
      .mockResolvedValue(mockUsersList);

    render(<PenggunaPage />);

    // Error state rendered
    await waitFor(() => {
      expect(screen.getByText("Failed to load users")).toBeDefined();
      expect(screen.getByText("Koneksi terputus")).toBeDefined();
    });

    // Click Coba Lagi -> Retry
    const retryBtn = screen.getByRole("button", { name: "Retry" });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(getUsersSpy).toHaveBeenCalledTimes(2);
      expect(screen.getByText("admin_super")).toBeDefined();
      expect(screen.queryByText("Failed to load users")).toBeNull();
    });

    // Test Refresh button
    const refreshBtn = screen.getByRole("button", { name: "Refresh" });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(getUsersSpy).toHaveBeenCalledTimes(3);
    });
  });
});
