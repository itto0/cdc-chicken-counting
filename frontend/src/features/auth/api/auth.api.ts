import { http } from "@/lib/http";
import type { LoginCredentials, LoginResponse, User } from "../types";

export const authApi = {
  login: (credentials: LoginCredentials): Promise<LoginResponse> =>
    http<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    }),

  getMe: (): Promise<User> =>
    http<User>("/api/v1/auth/me", {
      method: "GET",
    }),
};
