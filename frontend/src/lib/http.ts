import { env } from "@/config/env";

const TOKEN_KEY = "lihat_auth_token";

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // ignore
  }
}

export async function http<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const base = env.API_BASE_URL.replace(/\/$/, "");
  const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = endpoint.startsWith("http://") || endpoint.startsWith("https://")
    ? endpoint
    : `${base}${normalizedEndpoint}`;

  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401 || (response.status === 404 && endpoint.includes("/auth/me"))) {
    // If request to /me or protected resource failed with 401, clear stale token
    if (!endpoint.includes("/auth/login")) {
      setAuthToken(null);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("auth:unauthorized"));
      }
    }
  }

  if (!response.ok) {
    const errorText = await response.text();
    let parsedMessage = `HTTP error! status: ${response.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (typeof parsed.detail === "string") {
        parsedMessage = parsed.detail;
      } else if (parsed.detail) {
        parsedMessage = JSON.stringify(parsed.detail);
      }
    } catch {
      if (errorText) parsedMessage = errorText;
    }
    throw new Error(parsedMessage);
  }

  if (response.status === 204) return null as T;
  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (null as T);
}
