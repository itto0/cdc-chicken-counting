export function formatApiBaseUrl(url: string | undefined): string {
  if (!url) return "";
  const trimmed = url.trim();
  if (trimmed === "" || trimmed.startsWith("/")) return trimmed;
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return `https://${trimmed}`;
  }
  return trimmed;
}

export const env = {
  API_BASE_URL: formatApiBaseUrl(import.meta.env.VITE_API_BASE_URL),
  APP_NAME: "Lihat.id · Poultry Counter",
};

export const API_BASE_URL = env.API_BASE_URL;


