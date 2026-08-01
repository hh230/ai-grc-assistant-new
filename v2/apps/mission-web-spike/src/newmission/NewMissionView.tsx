import { useMemo, useState } from "react";

import { MissionApiClient, type MissionCreated } from "../api/client";
import { frameworkFor, typeLabel } from "../labels";
import { MISSION_TYPES } from "./missionTypes";

// New Mission — "What work should we start?" Two steps: pick a type + scope (a Presentation-State
// form, NOT a persisted Draft), then a **Mission Created review station** — a summary + the plan,
// with Start / Back. Human reviews before execution; the Core created a real Mission, not a draft.
type Phase =
  | { step: "form" }
  | { step: "created"; created: MissionCreated }
  | { step: "starting" };

const START_DWELL_MS = 700; // a beat of "Starting mission…" so a fast run doesn't feel like nothing

export function NewMissionView({
  onStarted,
  onCancel,
}: {
  onStarted: (missionId: string) => void;
  onCancel: () => void;
}) {
  const client = useMemo(() => new MissionApiClient(), []);
  const [type, setType] = useState(MISSION_TYPES[0].id);
  const [scope, setScope] = useState("");
  const [phase, setPhase] = useState<Phase>({ step: "form" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  const create = () =>
    run(async () => {
      const created = await client.createMission({ type, scope: scope.trim() });
      setPhase({ step: "created", created });
      setBusy(false);
    });

  const start = (missionId: string) =>
    run(async () => {
      setPhase({ step: "starting" });
      await client.startMission(missionId);
      // Dwell briefly on "Starting mission…" so a sub-second run still feels like something happened.
      window.setTimeout(() => onStarted(missionId), START_DWELL_MS);
    });

  return (
    <section className="newmission">
      <header className="newmission__header">
        <h1>New Mission</h1>
        <p className="newmission__subtitle">What work should we start?</p>
      </header>

      {phase.step === "form" && (
        <MissionForm
          type={type}
          scope={scope}
          busy={busy}
          error={error}
          onType={setType}
          onScope={setScope}
          onCreate={create}
          onCancel={onCancel}
        />
      )}

      {phase.step === "created" && (
        <MissionCreated
          created={phase.created}
          busy={busy}
          error={error}
          onStart={() => start(phase.created.mission.id)}
          onBack={() => {
            setError(null);
            setPhase({ step: "form" });
          }}
        />
      )}

      {phase.step === "starting" && <p className="newmission__starting">Starting mission…</p>}
    </section>
  );
}

function MissionForm({
  type,
  scope,
  busy,
  error,
  onType,
  onScope,
  onCreate,
  onCancel,
}: {
  type: string;
  scope: string;
  busy: boolean;
  error: string | null;
  onType: (t: string) => void;
  onScope: (s: string) => void;
  onCreate: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="mform">
      <label className="mform__label">Type of work</label>
      <ul className="mform__types">
        {MISSION_TYPES.map((t) => (
          <li key={t.id}>
            <button
              className={`mtype ${t.id === type ? "mtype--active" : ""}`}
              onClick={() => onType(t.id)}
            >
              <span className="mtype__label">{t.label}</span>
              <span className="mtype__blurb">{t.blurb}</span>
            </button>
          </li>
        ))}
      </ul>

      {/* #4 — answer the user's real question ("what will this assess against?") as part of the
          story, for the types that genuinely run against a standard. We *show* the framework the
          system already has; we do not add a picker (there is exactly one framework as data today). */}
      <FrameworkNote type={type} />

      <label className="mform__label" htmlFor="scope">
        Scope
      </label>
      <input
        id="scope"
        className="mform__scope"
        placeholder="e.g. Technological controls"
        value={scope}
        onChange={(e) => onScope(e.target.value)}
      />

      {error !== null && <p className="newmission__error">{error}</p>}

      <div className="mform__actions">
        <button
          className="newmission__primary"
          disabled={busy || scope.trim() === ""}
          onClick={onCreate}
        >
          {busy ? "Creating…" : "Create"}
        </button>
        <button className="newmission__secondary" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
        {/* #5 — say what unlocks Create, so a disabled button never looks broken. */}
        {scope.trim() === "" && !busy && (
          <span className="mform__hint">Enter a scope to continue.</span>
        )}
      </div>
    </div>
  );
}

function MissionCreated({
  created,
  busy,
  error,
  onStart,
  onBack,
}: {
  created: MissionCreated;
  busy: boolean;
  error: string | null;
  onStart: () => void;
  onBack: () => void;
}) {
  // The review station: a summary answers "what did I create?" first, then the plan answers "how?".
  // Start is the sole primary; Back the only other action. Human reviews before execution.
  const { mission, steps, human_approvals } = created;
  const framework = frameworkFor(mission.type);
  return (
    <div className="mcreated">
      <div className="mcreated__banner">Mission created — review the execution plan.</div>
      <dl className="mcreated__facts">
        <dt>Mission</dt>
        <dd>{typeLabel(mission.type)}</dd>
        <dt>Scope</dt>
        <dd>{mission.scope}</dd>
        {/* #4 — repeat the framework in the same language, so the user knows what it was measured
            against (and why the framework appears in the Result later). */}
        {framework !== null && (
          <>
            <dt>Assessment framework</dt>
            <dd>{framework}</dd>
          </>
        )}
        <dt>Steps</dt>
        <dd>{steps}</dd>
        <dt>Human approvals</dt>
        <dd>{human_approvals === 0 ? "None" : human_approvals}</dd>
      </dl>

      <h2 className="mcreated__plan-title">Execution plan</h2>
      <ol className="mcreated__plan">
        {mission.plan.map((step) => (
          <li key={step.id}>{step.description}</li>
        ))}
      </ol>

      {error !== null && <p className="newmission__error">{error}</p>}

      <div className="mform__actions">
        <button className="newmission__primary" disabled={busy} onClick={onStart}>
          Start mission
        </button>
        <button className="newmission__secondary" disabled={busy} onClick={onBack}>
          Back
        </button>
      </div>
    </div>
  );
}

// The framework narrative on the creation form — shown only for types that assess against a
// standard. It reads as a sentence, not a bare label: the user learns *what will be assessed against*.
function FrameworkNote({ type }: { type: string }) {
  const framework = frameworkFor(type);
  if (framework === null) return null;
  return (
    <div className="mform__framework">
      <span className="mform__framework-label">Assessment framework</span>
      <span className="mform__framework-value">{framework}</span>
      <span className="mform__framework-sub">
        This {typeLabel(type)} will evaluate your evidence against {framework}.
      </span>
    </div>
  );
}
