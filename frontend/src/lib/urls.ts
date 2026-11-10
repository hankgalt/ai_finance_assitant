const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;
const applicationBasePath = (
  import.meta.env.VITE_APPLICATION_BASE_PATH ?? import.meta.env.BASE_URL
).replace(/\/$/, "");

export function apiUrl(path: string): string {
  const base = configuredApiBaseUrl?.replace(/\/$/, "") ?? applicationBasePath;
  return `${base}${path}`;
}

export const appBasePath = applicationBasePath || "/";
