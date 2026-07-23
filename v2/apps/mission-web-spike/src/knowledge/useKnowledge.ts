// The thin React bridge to the Knowledge Presenter. The component calls this hook and gets a
// declarative state + actions; it never touches the API client or polling directly.

import { useEffect, useMemo, useState } from "react";

import { MissionApiClient } from "../api/client";
import { KnowledgePresenter, type KnowledgeState } from "./presenter";

export interface KnowledgeModel {
  state: KnowledgeState;
  upload: (evidenceKind: string, file: File) => Promise<void>;
  reload: () => void;
}

export function useKnowledge(): KnowledgeModel {
  const presenter = useMemo(() => new KnowledgePresenter(new MissionApiClient()), []);
  const [state, setState] = useState<KnowledgeState>(presenter.getState());

  useEffect(() => {
    const unsubscribe = presenter.subscribe(setState);
    void presenter.start();
    return () => {
      presenter.stop();
      unsubscribe();
    };
  }, [presenter]);

  return {
    state,
    upload: (evidenceKind, file) => presenter.upload(evidenceKind, file),
    reload: () => void presenter.start(),
  };
}
