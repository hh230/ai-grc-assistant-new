// #1 — a brand-new user lands in a data-filled Dashboard with no orientation ("where do I begin?").
// The Dashboard answers "what needs my attention?" — the wrong question for someone who hasn't started.
// So we do NOT change the Dashboard; we add a narrative layer ON TOP, shown at FIRST entry only, then
// dismissed for good. It names what Rasheed is, what a Mission is, and the three first steps — and its
// primary action is "Add evidence", because a mission with no evidence is the empty result the user
// would otherwise hit first.
export function FirstRunOverlay({
  onAddEvidence,
  onStartMission,
  onDismiss,
}: {
  onAddEvidence: () => void;
  onStartMission: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="firstrun" role="dialog" aria-modal="true" aria-labelledby="firstrun-title">
      <div className="firstrun__card">
        <h1 id="firstrun-title" className="firstrun__title">
          Welcome to Rasheed
        </h1>
        <p className="firstrun__lede">
          Rasheed is your AI GRC workspace. Work happens as <strong>Missions</strong> — governed,
          auditable units of GRC work (a gap assessment, a policy, a vendor review) that run on{" "}
          <strong>your own evidence</strong> and always show their sources.
        </p>
        <ol className="firstrun__steps">
          <li>
            <strong>Add your evidence</strong> — upload your policies, procedures, and reports.
          </li>
          <li>
            <strong>Start a mission</strong> — pick the work; Rasheed plans it, and you review the plan
            before it runs.
          </li>
          <li>
            <strong>Review the result</strong> — read what it found, with citations, and make the call.
          </li>
        </ol>
        <div className="firstrun__actions">
          <button className="firstrun__primary" onClick={onAddEvidence}>
            Add evidence
          </button>
          <button className="firstrun__secondary" onClick={onStartMission}>
            Start a mission
          </button>
          <button className="firstrun__ghost" onClick={onDismiss}>
            Skip for now
          </button>
        </div>
      </div>
    </div>
  );
}
