// The Result **presentation** layer — the front-end counterpart of the backend's
// DeliverableBuilderRegistry (owner's rule). The page never `switch(content.kind)`s: it asks the
// registry for the presenter, and the presenter decides how the content renders AND which export
// formats it offers. A new result type is a new presenter (an *addition*), never a page edit — the
// same "new type = addition, not modification" the whole project follows. (This is Presentation
// language, not Application — so it is outside the Application Contract Freeze.)

import type { ReactNode } from "react";

import type { ResultContent, ResultView } from "../api/client";

export interface ResultPresenter {
  Content: (props: { result: ResultView }) => ReactNode;
  availableExports: string[];
}

function Sections({ result }: { result: ResultView }) {
  return (
    <div className="rsections">
      {result.content.sections.map((s) => (
        <section key={s.heading} className="rsection">
          <div className="rsection__head">
            <h3>{s.heading}</h3>
            {s.confidence !== null && (
              <span className="rsection__conf">Confidence: {confidenceLabel(s.confidence)}</span>
            )}
          </div>
          <p>{s.body}</p>
          {s.citations.length > 0 && <span className="rsection__cite">{s.citations.join(" · ")}</span>}
        </section>
      ))}
    </div>
  );
}

// Generic result: just the narrative sections.
function GenericContentView({ result }: { result: ResultView }) {
  return <Sections result={result} />;
}

// Gap Assessment: the Coverage block, then Exceptions/Gaps, then the sections (evidence-first).
function GapContentView({ result }: { result: ResultView }) {
  const content = result.content;
  if (content.kind !== "gap_assessment") return <Sections result={result} />;
  const cov = content.coverage;
  const gaps = cov.gaps.filter((g) => !g.covered);
  return (
    <>
      <div className="coverage">
        <span>
          Framework: <strong>{cov.framework}</strong>
        </span>
        <span>
          Coverage: <strong>{Math.round(cov.coverage * 100)}%</strong> ({cov.covered_count}/{cov.total})
        </span>
        <span className="coverage__note">Evidence Mapping — not a compliance attestation</span>
      </div>
      {gaps.length > 0 && (
        <div className="gaps">
          <h3>Exceptions / Gaps</h3>
          <ul>
            {gaps.map((g) => (
              <li key={g.control_code}>
                <strong>{g.control_code}</strong> {g.control_title}
              </li>
            ))}
          </ul>
        </div>
      )}
      <Sections result={result} />
    </>
  );
}

const GENERIC_PRESENTER: ResultPresenter = {
  Content: GenericContentView,
  availableExports: ["md", "docx", "pdf"],
};

const GAP_PRESENTER: ResultPresenter = {
  Content: GapContentView,
  availableExports: ["md", "docx", "pdf"],
};

export class ResultPresenterRegistry {
  private readonly byKind: Record<string, ResultPresenter> = {
    generic: GENERIC_PRESENTER,
    gap_assessment: GAP_PRESENTER,
  };

  forContent(content: ResultContent): ResultPresenter {
    return this.byKind[content.kind] ?? GENERIC_PRESENTER;
  }
}

function confidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.5) return "Medium";
  return "Low";
}
