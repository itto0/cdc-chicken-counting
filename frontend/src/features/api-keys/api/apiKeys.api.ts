import { http } from "@/lib/http";
import type { ApiKeyItem, CreateApiKeyPayload, CreateApiKeyResponse } from "../types";

export const apiKeysApi = {
  getApiKeys: (): Promise<ApiKeyItem[]> =>
    http<ApiKeyItem[]>("/api/v1/auth/api-keys", {
      method: "GET",
    }),

  createApiKey: (payload: CreateApiKeyPayload): Promise<CreateApiKeyResponse> =>
    http<CreateApiKeyResponse>("/api/v1/auth/api-keys", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  revokeApiKey: (keyId: string): Promise<ApiKeyItem> =>
    http<ApiKeyItem>(`/api/v1/auth/api-keys/${keyId}`, {
      method: "DELETE",
    }),
};
