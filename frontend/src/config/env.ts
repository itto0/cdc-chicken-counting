export const env = {
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL !== undefined ? import.meta.env.VITE_API_BASE_URL : "",
  APP_NAME: "Lihat.id · Poultry Counter",
};

export const API_BASE_URL = env.API_BASE_URL;

