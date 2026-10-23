export interface UserItem {
  id: number;
  username: string;
  role: "admin" | "operator";
  is_active: boolean;
}

export interface CreateUserPayload {
  username: string;
  password: string;
  role: "admin" | "operator";
  is_active?: boolean;
}

export interface UpdateUserPayload {
  role?: "admin" | "operator";
  is_active?: boolean;
}

export interface AdminResetPasswordPayload {
  new_password: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}
