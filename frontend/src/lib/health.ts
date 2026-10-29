import { api } from "./api";
import type { HealthSummary } from "../types/contracts";

export async function fetchHealth(
  signal?: AbortSignal,
): Promise<HealthSummary> {
  return api.health(signal) as Promise<HealthSummary>;
}
