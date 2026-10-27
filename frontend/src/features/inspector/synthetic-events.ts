import fixture from "../../../../contracts/fixtures/run-events.synthetic.v1.json";

import type { RunEvent } from "../../types/contracts";

// The backend contract suite validates this same versioned JSON fixture with Pydantic.
export const syntheticRunEvents = fixture as RunEvent[];
