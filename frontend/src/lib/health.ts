import type { HealthSummary } from "../types/contracts";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchHealth(
  signal?: AbortSignal,
): Promise<HealthSummary> {
  const response = await fetch(apiBaseUrl + "/api/health", {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Health request failed with status " + response.status);
  }

  return (await response.json()) as HealthSummary;
}
