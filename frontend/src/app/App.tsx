import { useState } from "react";

import { HealthStatus } from "../features/health/HealthStatus";
import { InspectorPlaceholder } from "../features/inspector/InspectorPlaceholder";

type PageId = "chat" | "portfolio" | "market" | "goals" | "inspector";

const pages: Array<{
  id: PageId;
  label: string;
  title: string;
  description: string;
  milestone: string;
}> = [
  {
    id: "chat",
    label: "Assistant",
    title: "Conversational Assistant",
    description:
      "The conversation workflow is intentionally unavailable in M0. This shell establishes the future product surface.",
    milestone: "M4–M6",
  },
  {
    id: "portfolio",
    label: "Portfolio",
    title: "Investment Portfolio Dashboard",
    description:
      "Import, enrichment, and deterministic portfolio analysis are planned for M2 and M6.",
    milestone: "M2 · M6",
  },
  {
    id: "market",
    label: "Market",
    title: "Market Overview",
    description:
      "No live or fixture prices are shown here. Provider-backed market behavior begins in M3.",
    milestone: "M3 · M6",
  },
  {
    id: "goals",
    label: "Goals",
    title: "Financial Goal Planning",
    description:
      "Goal calculations remain a deterministic backend module scheduled for M2.",
    milestone: "M2 · M6",
  },
  {
    id: "inspector",
    label: "Inspector",
    title: "Agent Execution Inspector",
    description:
      "M0 defines the event contract with explicitly synthetic test data.",
    milestone: "M0 · M4 · M7",
  },
];

export function App() {
  const [activePage, setActivePage] = useState<PageId>("chat");
  const selectedPage =
    pages.find((page) => page.id === activePage) ?? pages[0]!;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <div>
          <p className="brand-kicker">AI Finance Assistant</p>
          <h1>Product foundation</h1>
        </div>
        <HealthStatus />
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <p className="sidebar-label">Experiences</p>
          <nav aria-label="Primary navigation">
            {pages.map((page) => (
              <button
                aria-current={page.id === activePage ? "page" : undefined}
                className={
                  page.id === activePage ? "nav-item active" : "nav-item"
                }
                key={page.id}
                onClick={() => setActivePage(page.id)}
                type="button"
              >
                <span>{page.label}</span>
                <small>{page.milestone}</small>
              </button>
            ))}
          </nav>
          <div className="local-note">
            <strong>Local M0 mode</strong>
            <span>No authentication, live data, or financial analysis.</span>
          </div>
        </aside>

        <main id="main-content" tabIndex={-1}>
          <header className="page-header">
            <div>
              <p className="eyebrow">Foundation shell</p>
              <h2>{selectedPage.title}</h2>
              <p>{selectedPage.description}</p>
            </div>
            <span className="milestone-chip">{selectedPage.milestone}</span>
          </header>

          {activePage === "inspector" ? (
            <InspectorPlaceholder />
          ) : (
            <section
              className="empty-state"
              aria-label={selectedPage.label + " status"}
            >
              <div className="empty-icon" aria-hidden="true">
                +
              </div>
              <h3>Interface reserved</h3>
              <p>
                This page is navigation and layout only. It does not imply that
                its later-milestone behavior exists.
              </p>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
