export interface ApiKeyItem {
  id: string;
  name: string;
  prefix: string;
  role: "OPERATOR" | "ADMIN";
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface CreateApiKeyPayload {
  name: string;
  role: "OPERATOR" | "ADMIN";
}

export interface CreateApiKeyResponse {
  id: string;
  name: string;
  api_key: string;
  prefix: string;
  role: "OPERATOR" | "ADMIN";
  created_at: string;
}
