import { useState } from "react";

import { MissionsView } from "./MissionsView";
import { DashboardView } from "./dashboard/DashboardView";
import { DecisionsView } from "./decisions/DecisionsView";
import { KnowledgeView } from "./knowledge/KnowledgeView";
import { MissionDetailView } from "./mission/MissionDetailView";
import { NewMissionView } from "./newmission/NewMissionView";
import { FirstRunOverlay } from "./onboarding/FirstRunOverlay";
import { ResultPage } from "./result/ResultPage";

// #1 — the first-use overlay shows once, then never again. A tiny guarded localStorage flag (the spike
// has no user store); a real app records "onboarded" on the account.
const WELCOMED_KEY = "rasheed.welcomed";

function hasBeenWelcomed(): boolean {
  try {
    return localStorage.getItem(WELCOMED_KEY) === "1";
  } catch {
    return false;
  }
}

function markWelcomed(): void {
  try {
    localStorage.setItem(WELCOMED_KEY, "1");
  } catch {
    /* private mode / no storage — the overlay simply shows again next time; harmless. */
  }
}

// Minimal navigation for the spike: a left rail switches Product Areas (Dashboard · Missions ·
// Evidence); Dashboard is the landing. Within Missions the flow drills list → detail → result. (A
// real app uses a router; the spike keeps it to one piece of state.)
type Nav =
  | { page: "dashboard" }
  | { page: "list"; status?: string; type?: string }
  | { page: "detail"; missionId: string; from?: Nav; tab?: "Evidence" }
  | { page: "result"; missionId: string }
  | { page: "decisions" }
  | { page: "knowledge" }
  | { page: "newmission" };

// Back keeps context: a mission opened from Decisions returns to Decisions, not the Mission List.
function backLabelFor(from: Nav | undefined): string {
  if (from?.page === "decisions") return "← Decisions";
  if (from?.page === "dashboard") return "← Dashboard";
  return "← Missions";
}

export function App() {
  const [nav, setNav] = useState<Nav>({ page: "dashboard" });
  const [showWelcome, setShowWelcome] = useState(() => !hasBeenWelcomed());

  // Dismiss the overlay for good, optionally sending the user to their chosen first step.
  function leaveWelcome(next?: Nav): void {
    markWelcomed();
    setShowWelcome(false);
    if (next) setNav(next);
  }

  const area =
    nav.page === "dashboard"
      ? "dashboard"
      : nav.page === "decisions"
        ? "decisions"
        : nav.page === "knowledge"
          ? "knowledge"
          : "missions";

  return (
    <div className="workspace">
      <nav className="rail">
        <div className="rail__brand">Rasheed</div>
        <button
          className={`rail__item ${area === "dashboard" ? "rail__item--active" : ""}`}
          onClick={() => setNav({ page: "dashboard" })}
        >
          Dashboard
        </button>
        <button
          className={`rail__item ${area === "missions" ? "rail__item--active" : ""}`}
          onClick={() => setNav({ page: "list" })}
        >
          Missions
        </button>
        <button
          className={`rail__item ${area === "decisions" ? "rail__item--active" : ""}`}
          onClick={() => setNav({ page: "decisions" })}
        >
          Decisions
        </button>
        <button
          className={`rail__item ${area === "knowledge" ? "rail__item--active" : ""}`}
          onClick={() => setNav({ page: "knowledge" })}
        >
          Evidence
        </button>
      </nav>

      <main className="app">
        {nav.page === "dashboard" && (
          <DashboardView
            onOpenMissions={(filter) => setNav({ page: "list", ...filter })}
            onOpenMission={(missionId) =>
              setNav({ page: "detail", missionId, from: { page: "dashboard" } })
            }
            onNewMission={() => setNav({ page: "newmission" })}
          />
        )}
        {nav.page === "list" && (
          <MissionsView
            initialStatus={nav.status}
            initialType={nav.type}
            onOpen={(missionId) => setNav({ page: "detail", missionId, from: nav })}
            onNewMission={() => setNav({ page: "newmission" })}
          />
        )}
        {nav.page === "detail" && (
          <MissionDetailView
            missionId={nav.missionId}
            onBack={() => setNav(nav.from ?? { page: "list" })}
            onOpenResult={(missionId) => setNav({ page: "result", missionId })}
            initialTab={nav.tab}
            backLabel={backLabelFor(nav.from)}
          />
        )}
        {nav.page === "result" && (
          <ResultPage
            missionId={nav.missionId}
            onBack={() => setNav({ page: "detail", missionId: nav.missionId })}
          />
        )}
        {nav.page === "decisions" && (
          <DecisionsView
            onOpenMission={(missionId) =>
              setNav({ page: "detail", missionId, from: { page: "decisions" } })
            }
            onReviewEvidence={(missionId) =>
              setNav({ page: "detail", missionId, from: { page: "decisions" }, tab: "Evidence" })
            }
          />
        )}
        {nav.page === "knowledge" && <KnowledgeView />}
        {nav.page === "newmission" && (
          <NewMissionView
            onStarted={(missionId) =>
              setNav({ page: "detail", missionId, from: { page: "list" } })
            }
            onCancel={() => setNav({ page: "list" })}
          />
        )}
      </main>

      {showWelcome && (
        <FirstRunOverlay
          onAddEvidence={() => leaveWelcome({ page: "knowledge" })}
          onStartMission={() => leaveWelcome({ page: "newmission" })}
          onDismiss={() => leaveWelcome()}
        />
      )}
    </div>
  );
}
