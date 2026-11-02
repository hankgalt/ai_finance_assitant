const workflowId = import.meta.env.VITE_WORKFLOW_ID;

if (!workflowId) {
  throw new Error("VITE_WORKFLOW_ID must be configured for frontend tests.");
}

export const TEST_WORKFLOW_ID = workflowId;
