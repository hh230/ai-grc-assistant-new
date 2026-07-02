"""Mappers for the Tenancy/Identity context."""

from __future__ import annotations

from grc_domain.shared.identifiers import OrganizationId, UserId
from grc_domain.tenancy.entities import Organization, User
from grc_domain.tenancy.enums import OrganizationStatus, UserRole, UserStatus
from grc_domain.tenancy.value_objects import Email, Region

from ..contracts.mapper import AggregateMapper
from ..models.tenancy import OrganizationModel, UserModel
from ._common import aware


class OrganizationMapper(AggregateMapper[Organization, OrganizationModel]):
    def to_orm(self, aggregate: Organization) -> OrganizationModel:
        return OrganizationModel(
            id=str(aggregate.id),
            name=aggregate.name,
            region=aggregate.region.code,
            status=aggregate.status.value,
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: OrganizationModel, aggregate: Organization) -> None:
        model.name = aggregate.name
        model.region = aggregate.region.code
        model.status = aggregate.status.value
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: OrganizationModel) -> Organization:
        return Organization(
            id=OrganizationId(model.id),
            name=model.name,
            region=Region(model.region),
            status=OrganizationStatus(model.status),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


class UserMapper(AggregateMapper[User, UserModel]):
    def to_orm(self, aggregate: User) -> UserModel:
        return UserModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            email=str(aggregate.email),
            display_name=aggregate.display_name,
            status=aggregate.status.value,
            roles=sorted(role.value for role in aggregate.roles),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: UserModel, aggregate: User) -> None:
        model.email = str(aggregate.email)
        model.display_name = aggregate.display_name
        model.status = aggregate.status.value
        model.roles = sorted(role.value for role in aggregate.roles)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: UserModel) -> User:
        return User(
            id=UserId(model.id),
            organization_id=OrganizationId(model.organization_id),
            email=Email(model.email),
            display_name=model.display_name,
            status=UserStatus(model.status),
            roles={UserRole(value) for value in model.roles},
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


organization_mapper = OrganizationMapper()
user_mapper = UserMapper()
