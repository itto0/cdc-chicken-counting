import { describe, it, expect, vi, beforeEach } from "vitest";
import { usersApi } from "../users.api";
import { http } from "@/lib/http";
import type {
  UserItem,
  CreateUserPayload,
  UpdateUserPayload,
  AdminResetPasswordPayload,
  ChangePasswordPayload,
} from "../../types";

vi.mock("@/lib/http", () => ({
  http: vi.fn(),
}));

describe("usersApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getUsers", () => {
    it("calls GET /api/v1/auth/users and returns list of users", async () => {
      const mockUsers: UserItem[] = [
        { id: 1, username: "admin", role: "admin", is_active: true },
        { id: 2, username: "operator1", role: "operator", is_active: false },
      ];
      vi.mocked(http).mockResolvedValueOnce(mockUsers);

      const result = await usersApi.getUsers();

      expect(http).toHaveBeenCalledTimes(1);
      expect(http).toHaveBeenCalledWith("/api/v1/auth/users");
      expect(result).toEqual(mockUsers);
    });
  });

  describe("createUser", () => {
    it("calls POST /api/v1/auth/users with serialized payload", async () => {
      const payload: CreateUserPayload = {
        username: "newuser",
        password: "secretpassword123",
        role: "operator",
        is_active: true,
      };
      const mockCreatedUser: UserItem = {
        id: 3,
        username: "newuser",
        role: "operator",
        is_active: true,
      };
      vi.mocked(http).mockResolvedValueOnce(mockCreatedUser);

      const result = await usersApi.createUser(payload);

      expect(http).toHaveBeenCalledTimes(1);
      expect(http).toHaveBeenCalledWith("/api/v1/auth/users", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockCreatedUser);
    });
  });

  describe("updateUser", () => {
    it("calls PUT /api/v1/auth/users/:userId with serialized payload", async () => {
      const payload: UpdateUserPayload = {
        role: "admin",
        is_active: false,
      };
      const mockUpdatedUser: UserItem = {
        id: 2,
        username: "operator1",
        role: "admin",
        is_active: false,
      };
      vi.mocked(http).mockResolvedValueOnce(mockUpdatedUser);

      const result = await usersApi.updateUser(2, payload);

      expect(http).toHaveBeenCalledTimes(1);
      expect(http).toHaveBeenCalledWith("/api/v1/auth/users/2", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockUpdatedUser);
    });
  });

  describe("resetPassword", () => {
    it("calls PUT /api/v1/auth/users/:userId/password with new_password payload", async () => {
      const payload: AdminResetPasswordPayload = {
        new_password: "newAdminResetPassword456",
      };
      const mockResponse = { message: "Password berhasil direset" };
      vi.mocked(http).mockResolvedValueOnce(mockResponse);

      const result = await usersApi.resetPassword(5, payload);

      expect(http).toHaveBeenCalledTimes(1);
      expect(http).toHaveBeenCalledWith("/api/v1/auth/users/5/password", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("deleteUser", () => {
    it("calls DELETE /api/v1/auth/users/:userId", async () => {
      const mockResponse = { message: "Pengguna berhasil dihapus" };
      vi.mocked(http).mockResolvedValueOnce(mockResponse);

      const result = await usersApi.deleteUser(4);

      expect(http).toHaveBeenCalledTimes(1);
      expect(http).toHaveBeenCalledWith("/api/v1/auth/users/4", {
        method: "DELETE",
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("changePassword", () => {
    it("calls PUT /api/v1/auth/password with current and new password payload", async () => {
      const payload: ChangePasswordPayload = {
        current_password: "oldPassword123",
        new_password: "newSecurePassword789",
      };
      const mockResponse = { message: "Password berhasil diperbarui" };
      vi.mocked(http).mockResolvedValueOnce(mockResponse);

      const result = await usersApi.changePassword(payload);

      expect(http).toHaveBeenCalledTimes(1);
      expect(http).toHaveBeenCalledWith("/api/v1/auth/password", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });
});
