# AI Finance Assistant glossary

**Account:** A user-declared financial container, such as a taxable brokerage account, traditional IRA, or Roth IRA. It is not an application login.

**Agent:** One of the six named LangGraph specialists that interprets a request, selects allowed tools, and returns a structured result. An agent is not the authority for financial arithmetic.

**Collection version:** An immutable, validated snapshot of one logical knowledge base that can be activated or rolled back as a unit.

**Cash-flow summary:** A minimized, authorized deterministic summary of income, spending, surplus, trends, coverage, and warnings. It excludes raw transaction descriptions and is the only planned cash-flow shape available to Goal Planning.

**Cash-flow import profile:** A versioned mapping from a bank or credit-card export's columns and date, amount, sign, and category conventions to canonical cash-flow transaction fields. It does not imply a live connection to the financial institution.

**Coursework release:** The product release submitted for the capstone, including all mandatory rubric evidence.

**Evidence:** Source material and provenance used to support an educational or analytical statement.

**Financial account:** See Account.

**Holding:** A position in a security or other asset within one Account at a stated quantity and currency.

**Goal projection:** A deterministic hypothetical calculation using explicit starting resources, contributions, horizon, return, inflation, and fee assumptions. It is an illustration, not a forecast or guarantee.

**Imported portfolio data:** User-supplied portfolio, account, and holding fields before external enrichment or calculation.

**Initial release:** The first usable product increment: six agents, investment portfolio analysis, education retrieval, market and news integrations, goal projections, web experiences, and execution inspection.

**Knowledge base:** A logical, source-governed body of content with its own metadata rules and collection versions. Finance Education and Tax Education are separate knowledge bases.

**Portfolio:** A user-defined set of one or more Accounts and their Holdings.

**Portfolio snapshot:** A time-specific analytical result created from imported portfolio data, provider-enriched security information, and deterministic calculations.

**Private demonstration release:** A production-oriented release operated only in a controlled local or private environment for the owner and approved viewers. It is not a public multi-user deployment.

**Pricing provenance:** The provider, retrieval time, market-data time, delay status, and cache status associated with a price.

**Durable provider cache:** A server-side store of normalized provider observations retained across application restarts for bounded reuse. It remains derived provider data with freshness and rights metadata, not an authoritative market-data warehouse.
_Avoid_: Market-data archive, source-of-truth price store

**Production hardening:** Controls required before operating as a public multi-user financial product, beyond the initial local release.

**Run:** One orchestrated execution of a user request. A Run has an execution identifier and belongs to a Session and Workflow.

**Security reference information:** Provider-supplied facts about an instrument, such as name, asset class, sector, currency, and expense ratio. It remains distinct from user input.

**Session:** An isolated conversational and application context belonging to one user context. A Session can contain multiple Runs.

**Source registry:** The governed inventory of permitted knowledge sources, their ownership or use terms, retrieval location, review cadence, and content status.

**Trace:** The privacy-filtered record of measured execution events for a Run. It excludes hidden model reasoning and sensitive payloads.

**Workflow:** A versioned LangGraph definition that routes and coordinates Agents and deterministic modules.

