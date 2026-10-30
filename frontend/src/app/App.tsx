import {
  Archive,
  Bot,
  ChartNoAxesCombined,
  Crosshair,
  History,
  Landmark,
  PanelLeftClose,
  Target,
} from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";

import { StateNotice } from "../components/StateNotice";
import { HealthStatus } from "../features/health/HealthStatus";
import { InspectorPlaceholder } from "../features/inspector/InspectorPlaceholder";
import { useSession } from "../hooks/useSession";
import { ClientApiError } from "../lib/api";
import { recordNavigation, type BrowserPage } from "../lib/telemetry";

type PageId =
  "assistant" | "portfolio" | "market" | "goals" | "history" | "inspector";

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
const SessionHistoryExperience = lazy(() =>
  import("../features/history/SessionHistoryExperience").then((module) => ({
    default: module.SessionHistoryExperience,
  })),
);

const pages = [
  { id: "assistant", label: "Assistant", icon: Bot },
  { id: "portfolio", label: "Portfolio", icon: Landmark },
  { id: "market", label: "Market", icon: ChartNoAxesCombined },
  { id: "goals", label: "Goals", icon: Target },
  { id: "history", label: "History", icon: History },
  { id: "inspector", label: "Inspector", icon: Crosshair },
] satisfies Array<{ id: PageId; label: string; icon: typeof Bot }>;

export function App() {
  const [activePage, setActivePage] = useState<PageId>("assistant");
  const [menuOpen, setMenuOpen] = useState(false);
  const [clearConfirmationOpen, setClearConfirmationOpen] = useState(false);
  const clearConfirmationRef = useRef<HTMLButtonElement>(null);
  const session = useSession();

  useEffect(() => {
    recordNavigation(activePage as BrowserPage);
  }, [activePage]);

  useEffect(() => {
    if (clearConfirmationOpen) clearConfirmationRef.current?.focus();
  }, [clearConfirmationOpen]);

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
        return (
          <PortfolioExperience
            key={session.data.session_id}
            sessionId={session.data.session_id}
          />
        );
      case "market":
        return (
          <MarketExperience
            key={session.data.session_id}
            sessionId={session.data.session_id}
          />
        );
      case "goals":
        return (
          <GoalExperience
            key={session.data.session_id}
            sessionId={session.data.session_id}
          />
        );
      case "history":
        return <SessionHistoryExperience />;
      case "inspector":
        return <InspectorPlaceholder />;
      default:
        return (
          <AssistantExperience
            key={session.data.session_id}
            sessionId={session.data.session_id}
          />
        );
    }
  })();

  const archiveActiveSession = async () => {
    try {
      await session.archiveActiveSession();
      setActivePage("assistant");
      setMenuOpen(false);
      setClearConfirmationOpen(false);
    } catch {
      // The hook exposes a safe user-facing error while preserving the active Session.
    }
  };

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
            {clearConfirmationOpen ? (
              <div
                aria-labelledby="clear-session-title"
                className="clear-session-confirmation"
                role="group"
              >
                <strong id="clear-session-title">
                  Archive active Session?
                </strong>
                <p>
                  Preserve this Session and its saved history as read-only, then
                  open a new empty Session. You can permanently delete it later
                  from History.
                </p>
                {session.archiveError ? (
                  <p className="clear-session-error" role="alert">
                    {session.archiveError instanceof ClientApiError
                      ? session.archiveError.message
                      : "The Session could not be archived. Please try again."}
                  </p>
                ) : null}
                <div className="clear-session-actions">
                  <button
                    className="primary-button"
                    disabled={session.isArchiving}
                    onClick={() => void archiveActiveSession()}
                    ref={clearConfirmationRef}
                    type="button"
                  >
                    {session.isArchiving
                      ? "Archiving Session…"
                      : "Archive and start fresh"}
                  </button>
                  <button
                    className="text-button"
                    disabled={session.isArchiving}
                    onClick={() => {
                      session.resetArchiveSession();
                      setClearConfirmationOpen(false);
                    }}
                    type="button"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                className="clear-session-button"
                disabled={!session.data || session.isArchiving}
                onClick={() => {
                  session.resetArchiveSession();
                  setClearConfirmationOpen(true);
                }}
                type="button"
              >
                <Archive aria-hidden="true" size={15} />
                Clear active session
              </button>
            )}
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
