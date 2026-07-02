"""Mappers for the Missions context — root plus child mappers for diff-based sync.

The :class:`MissionMapper` translates the root scalar columns. The mission's two child
collections (steps, approval gates) live in their own tables and are synchronized by the
repository's diff algorithm; each :class:`ChildMapper` here provides the stable diff key and
the per-row translation.
"""

from __future__ import annotations

from grc_domain.missions.entities import ApprovalGate, Mission, MissionStep
from grc_domain.missions.enums import ApprovalDecision, MissionStatus, MissionStepStatus
from grc_domain.missions.value_objects import MissionGoal
from grc_domain.platform.enums import ToolSideEffect
from grc_domain.shared.identifiers import (
    AgentId,
    ApprovalGateId,
    MissionId,
    MissionStepId,
    OrganizationId,
    ToolId,
    UserId,
    WorkspaceId,
)

from ..contracts.mapper import AggregateMapper, ChildMapper
from ..models.missions import MissionApprovalGateModel, MissionModel, MissionStepModel
from ._common import aware, decode_proposed_action, encode_proposed_action


class MissionStepChildMapper(ChildMapper[MissionStep, MissionStepModel]):
    def identity(self, child: MissionStep) -> str:
        return str(child.id)

    def orm_identity(self, model: MissionStepModel) -> str:
        return model.id

    def to_orm(self, child: MissionStep, parent_id: str, position: int) -> MissionStepModel:
        return MissionStepModel(
            id=str(child.id),
            mission_id=parent_id,
            position=position,
            name=child.name,
            side_effect=child.side_effect.value,
            agent_id=str(child.agent_id) if child.agent_id is not None else None,
            tool_ids=[str(tool_id) for tool_id in child.tool_ids],
            status=child.status.value,
            output_ref=child.output_ref,
            created_at=child.created_at,
            updated_at=child.updated_at,
        )

    def update_orm(self, model: MissionStepModel, child: MissionStep, position: int) -> None:
        model.position = position
        model.name = child.name
        model.side_effect = child.side_effect.value
        model.agent_id = str(child.agent_id) if child.agent_id is not None else None
        model.tool_ids = [str(tool_id) for tool_id in child.tool_ids]
        model.status = child.status.value
        model.output_ref = child.output_ref
        model.updated_at = child.updated_at

    def to_domain(self, model: MissionStepModel) -> MissionStep:
        return MissionStep(
            id=MissionStepId(model.id),
            name=model.name,
            side_effect=ToolSideEffect(model.side_effect),
            agent_id=AgentId(model.agent_id) if model.agent_id is not None else None,
            tool_ids=tuple(ToolId(value) for value in model.tool_ids),
            status=MissionStepStatus(model.status),
            output_ref=model.output_ref,
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


class MissionApprovalGateChildMapper(ChildMapper[ApprovalGate, MissionApprovalGateModel]):
    def identity(self, child: ApprovalGate) -> str:
        return str(child.id)

    def orm_identity(self, model: MissionApprovalGateModel) -> str:
        return model.id

    def to_orm(
        self, child: ApprovalGate, parent_id: str, position: int
    ) -> MissionApprovalGateModel:
        return MissionApprovalGateModel(
            id=str(child.id),
            mission_id=parent_id,
            position=position,
            step_id=str(child.step_id),
            proposed_action=encode_proposed_action(child.proposed_action),
            decision=child.decision.value,
            decided_by=str(child.decided_by) if child.decided_by is not None else None,
            rejection_reason=child.rejection_reason,
            created_at=child.created_at,
            updated_at=child.updated_at,
        )

    def update_orm(
        self, model: MissionApprovalGateModel, child: ApprovalGate, position: int
    ) -> None:
        model.position = position
        model.step_id = str(child.step_id)
        model.proposed_action = encode_proposed_action(child.proposed_action)
        model.decision = child.decision.value
        model.decided_by = str(child.decided_by) if child.decided_by is not None else None
        model.rejection_reason = child.rejection_reason
        model.updated_at = child.updated_at

    def to_domain(self, model: MissionApprovalGateModel) -> ApprovalGate:
        return ApprovalGate(
            id=ApprovalGateId(model.id),
            step_id=MissionStepId(model.step_id),
            proposed_action=decode_proposed_action(model.proposed_action),
            decision=ApprovalDecision(model.decision),
            decided_by=UserId(model.decided_by) if model.decided_by is not None else None,
            rejection_reason=model.rejection_reason,
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


mission_step_child_mapper = MissionStepChildMapper()
mission_gate_child_mapper = MissionApprovalGateChildMapper()


class MissionMapper(AggregateMapper[Mission, MissionModel]):
    def to_orm(self, aggregate: Mission) -> MissionModel:
        mission_id = str(aggregate.id)
        return MissionModel(
            id=mission_id,
            organization_id=str(aggregate.organization_id),
            workspace_id=str(aggregate.workspace_id),
            goal=aggregate.goal.statement,
            created_by=str(aggregate.created_by),
            owner_id=str(aggregate.owner_id),
            status=aggregate.status.value,
            failure_reason=aggregate.failure_reason,
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
            steps=[
                mission_step_child_mapper.to_orm(step, mission_id, index)
                for index, step in enumerate(aggregate.steps)
            ],
            gates=[
                mission_gate_child_mapper.to_orm(gate, mission_id, index)
                for index, gate in enumerate(aggregate.approval_gates)
            ],
        )

    def update_orm(self, model: MissionModel, aggregate: Mission) -> None:
        # Root scalar columns only — child collections are diff-synced by the repository.
        model.status = aggregate.status.value
        model.failure_reason = aggregate.failure_reason
        model.owner_id = str(aggregate.owner_id)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: MissionModel) -> Mission:
        return Mission(
            id=MissionId(model.id),
            organization_id=OrganizationId(model.organization_id),
            workspace_id=WorkspaceId(model.workspace_id),
            goal=MissionGoal(model.goal),
            created_by=UserId(model.created_by),
            owner_id=UserId(model.owner_id),
            status=MissionStatus(model.status),
            steps=[mission_step_child_mapper.to_domain(step) for step in model.steps],
            approval_gates=[mission_gate_child_mapper.to_domain(gate) for gate in model.gates],
            failure_reason=model.failure_reason,
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


mission_mapper = MissionMapper()
