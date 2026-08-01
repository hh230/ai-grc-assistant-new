"""The Application-layer language (ADR 0054): context, result, errors, projection port."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from mission_application import (
    ApplicationError,
    CommandContext,
    CommandResult,
    IllegalCommand,
    MissionNotFound,
    NotAuthorized,
    ProjectionPort,
)


def _ctx() -> CommandContext:
    return CommandContext(
        tenant_id="T", principal_id="approver@t", roles=("approver",), correlation_id="corr-1"
    )


def test_command_result_is_a_frozen_stable_shape() -> None:
    result = CommandResult(mission_id="m1", status="resumed", approval_pending=False)
    assert (result.mission_id, result.status, result.approval_pending) == ("m1", "resumed", False)
    with pytest.raises(FrozenInstanceError):  # frozen — outcomes are not mutated after the fact
        result.status = "completed"  # type: ignore[misc]


def test_approval_pending_defaults_false() -> None:
    assert CommandResult(mission_id="m1", status="completed").approval_pending is False


def test_errors_share_one_base() -> None:
    for err in (NotAuthorized, MissionNotFound, IllegalCommand):
        assert issubclass(err, ApplicationError)


def test_command_context_carries_explicit_identity_not_derived() -> None:
    ctx = _ctx()
    # principal + roles are first-class — NOT read off the tenant (a tenant is not a user).
    assert ctx.principal_id == "approver@t"
    assert ctx.roles == ("approver",)
    assert ctx.has_role("approver") and not ctx.has_role("admin")


def test_command_context_bridges_to_core_tenant_scope() -> None:
    tenant = _ctx().tenant_context()
    assert tenant.tenant_id == "T"
    assert tenant.principal_id == "approver@t"
    assert tenant.roles == ("approver",)


def test_command_context_clock_is_injectable() -> None:
    ctx = CommandContext(tenant_id="T", principal_id="p", clock=lambda: 123.0)
    assert ctx.clock() == 123.0


def test_projection_port_is_generic_and_structural() -> None:
    class _Spy:
        def __init__(self) -> None:
            self.seen: list[object] = []

        def project(self, subject: object) -> None:
            self.seen.append(subject)

    spy = _Spy()
    assert isinstance(spy, ProjectionPort)  # runtime_checkable structural port (generic)
    spy.project("anything")
    assert spy.seen == ["anything"]
