import {
  Bot,
  ChartNoAxesCombined,
  Crosshair,
  Landmark,
  PanelLeftClose,
  Target,
} from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";

import { StateNotice } from "../components/StateNotice";
import { HealthStatus } from "../features/health/HealthStatus";
import { InspectorPlaceholder } from "../features/inspector/InspectorPlaceholder";
import { useSession } from "../hooks/useSession";
import { recordNavigation, type BrowserPage } from "../lib/telemetry";

type PageId = "assistant" | "portfolio" | "market" | "goals" | "inspector";

const AssistantExperience = lazy(() =>
  import("../features/chat/AssistantExperience").then((module) => ({
    default: module.AssistantExperience,
  })),
);
const GoalExperience = lazy(() =>
  import("../features/goals/GoalExperience").then((module) => ({
    default: module.GoalExperience,
  })),
);
const MarketExperience = lazy(() =>
  import("../features/market/MarketExperience").then((module) => ({
    default: module.MarketExperience,
  })),
);
const PortfolioExperience = lazy(() =>
  import("../features/portfolio/PortfolioExperience").then((module) => ({
    default: module.PortfolioExperience,
  })),
);

const pages = [
  { id: "assistant", label: "Assistant", icon: Bot },
  { id: "portfolio", label: "Portfolio", icon: Landmark },
  { id: "market", label: "Market", icon: ChartNoAxesCombined },
  { id: "goals", label: "Goals", icon: Target },
  { id: "inspector", label: "Inspector", icon: Crosshair },
] satisfies Array<{ id: PageId; label: string; icon: typeof Bot }>;

export function App() {
  const [activePage, setActivePage] = useState<PageId>("assistant");
  const [menuOpen, setMenuOpen] = useState(false);
  const session = useSession();

  useEffect(() => {
    recordNavigation(activePage as BrowserPage);
  }, [activePage]);

  const content = (() => {
    if (session.isPending)
      return <StateNotice title="Opening your local demo session" />;
    if (session.isError) {
      return (
        <StateNotice tone="error" title="A local session could not be opened">
          <p>
            Start the FastAPI backend, then retry. No browser credential is
            required.
          </p>
          <button
            className="secondary-button"
            onClick={() => void session.refetch()}
            type="button"
          >
            Retry session
          </button>
        </StateNotice>
      );
    }
    switch (activePage) {
      case "portfolio":
        return <PortfolioExperience sessionId={session.data.session_id} />;
      case "market":
        return <MarketExperience sessionId={session.data.session_id} />;
      case "goals":
        return <GoalExperience sessionId={session.data.session_id} />;
      case "inspector":
        return <InspectorPlaceholder />;
      default:
        return <AssistantExperience sessionId={session.data.session_id} />;
    }
  })();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            AF
          </div>
          <div>
            <p>AI Finance Assistant</p>
            <span>Private demo workspace</span>
          </div>
        </div>
        <div className="topbar-actions">
          <HealthStatus />
          <button
            aria-expanded={menuOpen}
            aria-label="Toggle navigation"
            className="mobile-menu"
            onClick={() => setMenuOpen(!menuOpen)}
            type="button"
          >
            <PanelLeftClose size={20} />
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className={menuOpen ? "sidebar sidebar-open" : "sidebar"}>
          <p className="sidebar-label">Workspace</p>
          <nav aria-label="Primary navigation">
            {pages.map((page) => {
              const Icon = page.icon;
              return (
                <button
                  aria-current={page.id === activePage ? "page" : undefined}
                  className={
                    page.id === activePage ? "nav-item active" : "nav-item"
                  }
                  key={page.id}
                  onClick={() => {
                    setActivePage(page.id);
                    setMenuOpen(false);
                  }}
                  type="button"
                >
                  <Icon aria-hidden="true" size={19} />
                  <span>{page.label}</span>
                </button>
              );
            })}
          </nav>
          <div className="local-note">
            <strong>Owner-only local demo</strong>
            <span>
              Educational information. Imported financial data stays in the
              configured local application store.
            </span>
          </div>
        </aside>
        <main id="main-content" tabIndex={-1}>
          <Suspense fallback={<StateNotice title="Loading workspace" />}>
            {content}
          </Suspense>
        </main>
      </div>
    </div>
  );
}
