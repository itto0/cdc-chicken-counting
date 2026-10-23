import { http } from "@/lib/http";
import type {
  UserItem,
  CreateUserPayload,
  UpdateUserPayload,
  AdminResetPasswordPayload,
  ChangePasswordPayload,
} from "../types";

export const usersApi = {
  getUsers: async (): Promise<UserItem[]> => {
    return http<UserItem[]>("/api/v1/auth/users");
  },

  createUser: async (payload: CreateUserPayload): Promise<UserItem> => {
    return http<UserItem>("/api/v1/auth/users", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateUser: async (userId: number, payload: UpdateUserPayload): Promise<UserItem> => {
    return http<UserItem>(`/api/v1/auth/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  resetPassword: async (userId: number, payload: AdminResetPasswordPayload): Promise<{ message: string }> => {
    return http<{ message: string }>(`/api/v1/auth/users/${userId}/password`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  deleteUser: async (userId: number): Promise<{ message: string }> => {
    return http<{ message: string }>(`/api/v1/auth/users/${userId}`, {
      method: "DELETE",
    });
  },

  changePassword: async (payload: ChangePasswordPayload): Promise<{ message: string }> => {
    return http<{ message: string }>("/api/v1/auth/password", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
};
