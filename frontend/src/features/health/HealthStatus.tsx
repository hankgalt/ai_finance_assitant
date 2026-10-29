import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "../../lib/health";

export function HealthStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => fetchHealth(signal),
    retry: false,
    refetchInterval: false,
  });

  if (health.isPending) {
    return (
      <div className="status-pill status-pending" role="status">
        Checking backend
      </div>
    );
  }

  if (health.isError) {
    return (
      <div className="status-pill status-error" role="status">
        Backend disconnected
      </div>
    );
  }

  const ready = health.data.readiness.status === "ok";
  return (
    <div
      className={"status-pill " + (ready ? "status-ready" : "status-warning")}
      role="status"
    >
      {"API live · " + (ready ? "ready" : "limited")}
    </div>
  );
}
