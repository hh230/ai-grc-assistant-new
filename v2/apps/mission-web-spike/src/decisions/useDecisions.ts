// The thin React bridge to the Decisions Presenter. The component gets declarative state + actions and
// never touches the API client directly.

import { useEffect, useMemo, useState } from "react";

import { CURRENT_USER, MissionApiClient } from "../api/client";
import { DecisionsPresenter, type DecisionsState } from "./presenter";

export interface DecisionsModel {
  state: DecisionsState;
  canDecide: boolean;
  approve: (missionId: string, decisionId: string) => Promise<void>;
  reject: (missionId: string, decisionId: string) => Promise<void>;
  reload: () => void;
}

export function useDecisions(): DecisionsModel {
  const presenter = useMemo(
    () => new DecisionsPresenter(new MissionApiClient(), CURRENT_USER),
    [],
  );
  const [state, setState] = useState<DecisionsState>(presenter.getState());

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
    canDecide: presenter.canDecide,
    approve: (missionId, decisionId) => presenter.approve(missionId, decisionId),
    reject: (missionId, decisionId) => presenter.reject(missionId, decisionId),
    reload: () => presenter.reload(),
  };
}
