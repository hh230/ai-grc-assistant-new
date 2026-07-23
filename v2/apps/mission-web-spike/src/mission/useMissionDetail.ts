// The thin React bridge to the Presenter. The component calls this hook and gets a declarative state
// + actions; it never touches the API client or polling directly.

import { useEffect, useMemo, useState } from "react";

import { CURRENT_USER, MissionApiClient } from "../api/client";
import { MissionDetailPresenter, type DetailState } from "./presenter";

export interface MissionDetailModel {
  state: DetailState;
  canApprove: boolean;
  approve: (stepId: string, comment?: string) => Promise<void>;
  reject: (stepId: string, comment?: string) => Promise<void>;
}

export function useMissionDetail(missionId: string): MissionDetailModel {
  const presenter = useMemo(
    () => new MissionDetailPresenter(new MissionApiClient(), missionId, CURRENT_USER),
    [missionId],
  );
  const [state, setState] = useState<DetailState>(presenter.getState());

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
    canApprove: presenter.canApprove,
    approve: (stepId, comment) => presenter.approve(stepId, comment),
    reject: (stepId, comment) => presenter.reject(stepId, comment),
  };
}
