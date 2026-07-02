"""Use cases for the Assessment capability."""

from __future__ import annotations

from grc_domain.assessments.entities import Assessment
from grc_domain.assessments.value_objects import ControlAssessmentResult
from grc_domain.frameworks.value_objects import FrameworkVersion
from grc_domain.shared.identifiers import AssessmentId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import (
    CompleteAssessment,
    PlanAssessment,
    RecordAssessmentResult,
    StartAssessment,
)
from .dtos import AssessmentDTO
from .queries import GetAssessment, ListAssessments


async def _load(uow: UnitOfWork, ctx: ExecutionContext, assessment_id: AssessmentId) -> Assessment:
    a = await uow.assessments.get(ctx.organization_id, assessment_id)
    if a is None:
        raise ResourceNotFoundError(f"Assessment {assessment_id} not found")
    return a


class PlanAssessmentHandler(TransactionalCommandHandler[PlanAssessment, AssessmentDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.ASSESSMENT)
        assessment = Assessment.plan(
            id=AssessmentId.generate(),
            organization_id=context.organization_id,
            workspace_id=command.workspace_id,
            framework_id=command.framework_id,
            framework_version=FrameworkVersion(command.framework_version),
            assessment_type=command.assessment_type,
        )
        await uow.assessments.add(assessment)
        return AssessmentDTO.from_domain(assessment)


class StartAssessmentHandler(TransactionalCommandHandler[StartAssessment, AssessmentDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.ASSESSMENT, str(command.assessment_id)
        )
        assessment = await _load(uow, context, command.assessment_id)
        assessment.start()
        await uow.assessments.save(assessment)
        return AssessmentDTO.from_domain(assessment)


class RecordAssessmentResultHandler(
    TransactionalCommandHandler[RecordAssessmentResult, AssessmentDTO]
):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.ASSESSMENT, str(command.assessment_id)
        )
        assessment = await _load(uow, context, command.assessment_id)
        assessment.record_result(
            ControlAssessmentResult(
                framework_control_id=command.framework_control_id,
                coverage=command.coverage,
                satisfied_by_control_id=command.satisfied_by_control_id,
                notes=command.notes,
            )
        )
        await uow.assessments.save(assessment)
        return AssessmentDTO.from_domain(assessment)


class CompleteAssessmentHandler(TransactionalCommandHandler[CompleteAssessment, AssessmentDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.ASSESSMENT, str(command.assessment_id)
        )
        assessment = await _load(uow, context, command.assessment_id)
        assessment.complete()
        await uow.assessments.save(assessment)
        return AssessmentDTO.from_domain(assessment)


class GetAssessmentHandler(QueryHandler[GetAssessment, AssessmentDTO]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.ASSESSMENT, str(query.assessment_id)
        )
        async with self._uow as uow:
            a = await uow.assessments.get(context.organization_id, query.assessment_id)
        if a is None:
            raise ResourceNotFoundError(f"Assessment {query.assessment_id} not found")
        return AssessmentDTO.from_domain(a)


class ListAssessmentsHandler(QueryHandler[ListAssessments, list[AssessmentDTO]]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.READ, ResourceType.ASSESSMENT)
        async with self._uow as uow:
            items = await uow.assessments.list_for_organization(context.organization_id)
        return [AssessmentDTO.from_domain(a) for a in items]
