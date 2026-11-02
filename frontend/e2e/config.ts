import { fileURLToPath } from "node:url";

import { loadEnv } from "vite";

const frontendRoot = fileURLToPath(new URL("../", import.meta.url));
const testEnvironment = loadEnv("test", frontendRoot, "VITE_");
const workflowId =
  process.env.VITE_WORKFLOW_ID ?? testEnvironment.VITE_WORKFLOW_ID;

if (!workflowId) {
  throw new Error("VITE_WORKFLOW_ID must be configured for browser tests.");
}

export const E2E_WORKFLOW_ID = workflowId;
