"""Mappers for the Platform context (Tool / Agent / Plugin descriptors)."""

from __future__ import annotations

from grc_domain.platform.entities import AgentDescriptor, PluginDescriptor, ToolDescriptor
from grc_domain.platform.enums import (
    AgentStatus,
    AgentType,
    PluginStatus,
    ToolSideEffect,
    ToolStatus,
)
from grc_domain.shared.identifiers import AgentId, PluginId, ToolId
from grc_domain.shared.value_objects import SemanticVersion

from ..contracts.mapper import AggregateMapper
from ..models.platform import (
    AgentDescriptorModel,
    PluginDescriptorModel,
    ToolDescriptorModel,
)
from ._common import (
    aware,
    decode_permissions,
    decode_schema_ref,
    decode_version_range,
    encode_permissions,
    encode_schema_ref,
    encode_version_range,
)


class ToolDescriptorMapper(AggregateMapper[ToolDescriptor, ToolDescriptorModel]):
    def to_orm(self, aggregate: ToolDescriptor) -> ToolDescriptorModel:
        return ToolDescriptorModel(
            id=str(aggregate.id),
            name=aggregate.name,
            version_label=str(aggregate.version),
            description=aggregate.description,
            side_effect=aggregate.side_effect.value,
            status=aggregate.status.value,
            requires_approval=aggregate.requires_approval,
            required_permissions=encode_permissions(aggregate.required_permissions),
            input_schema=encode_schema_ref(aggregate.input_schema),
            output_schema=encode_schema_ref(aggregate.output_schema),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: ToolDescriptorModel, aggregate: ToolDescriptor) -> None:
        model.name = aggregate.name
        model.version_label = str(aggregate.version)
        model.description = aggregate.description
        model.side_effect = aggregate.side_effect.value
        model.status = aggregate.status.value
        model.requires_approval = aggregate.requires_approval
        model.required_permissions = encode_permissions(aggregate.required_permissions)
        model.input_schema = encode_schema_ref(aggregate.input_schema)
        model.output_schema = encode_schema_ref(aggregate.output_schema)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: ToolDescriptorModel) -> ToolDescriptor:
        return ToolDescriptor(
            id=ToolId(model.id),
            name=model.name,
            version=SemanticVersion.parse(model.version_label),
            description=model.description,
            side_effect=ToolSideEffect(model.side_effect),
            status=ToolStatus(model.status),
            requires_approval=model.requires_approval,
            required_permissions=decode_permissions(model.required_permissions),
            input_schema=decode_schema_ref(model.input_schema),
            output_schema=decode_schema_ref(model.output_schema),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


class AgentDescriptorMapper(AggregateMapper[AgentDescriptor, AgentDescriptorModel]):
    def to_orm(self, aggregate: AgentDescriptor) -> AgentDescriptorModel:
        return AgentDescriptorModel(
            id=str(aggregate.id),
            name=aggregate.name,
            agent_type=aggregate.agent_type.value,
            status=aggregate.status.value,
            allowed_tool_ids=sorted(str(tool_id) for tool_id in aggregate.allowed_tool_ids),
            data_scopes=sorted(aggregate.data_scopes),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: AgentDescriptorModel, aggregate: AgentDescriptor) -> None:
        model.name = aggregate.name
        model.agent_type = aggregate.agent_type.value
        model.status = aggregate.status.value
        model.allowed_tool_ids = sorted(str(tool_id) for tool_id in aggregate.allowed_tool_ids)
        model.data_scopes = sorted(aggregate.data_scopes)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: AgentDescriptorModel) -> AgentDescriptor:
        return AgentDescriptor(
            id=AgentId(model.id),
            name=model.name,
            agent_type=AgentType(model.agent_type),
            status=AgentStatus(model.status),
            allowed_tool_ids=frozenset(ToolId(value) for value in model.allowed_tool_ids),
            data_scopes=frozenset(model.data_scopes),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


class PluginDescriptorMapper(AggregateMapper[PluginDescriptor, PluginDescriptorModel]):
    def to_orm(self, aggregate: PluginDescriptor) -> PluginDescriptorModel:
        return PluginDescriptorModel(
            id=str(aggregate.id),
            name=aggregate.name,
            version_label=str(aggregate.version),
            status=aggregate.status.value,
            provided_tool_ids=sorted(str(tool_id) for tool_id in aggregate.provided_tool_ids),
            provided_agent_ids=sorted(str(agent_id) for agent_id in aggregate.provided_agent_ids),
            required_permissions=encode_permissions(aggregate.required_permissions),
            compatibility=encode_version_range(aggregate.compatibility),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: PluginDescriptorModel, aggregate: PluginDescriptor) -> None:
        model.name = aggregate.name
        model.version_label = str(aggregate.version)
        model.status = aggregate.status.value
        model.provided_tool_ids = sorted(str(tool_id) for tool_id in aggregate.provided_tool_ids)
        model.provided_agent_ids = sorted(
            str(agent_id) for agent_id in aggregate.provided_agent_ids
        )
        model.required_permissions = encode_permissions(aggregate.required_permissions)
        model.compatibility = encode_version_range(aggregate.compatibility)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: PluginDescriptorModel) -> PluginDescriptor:
        return PluginDescriptor(
            id=PluginId(model.id),
            name=model.name,
            version=SemanticVersion.parse(model.version_label),
            status=PluginStatus(model.status),
            provided_tool_ids=frozenset(ToolId(value) for value in model.provided_tool_ids),
            provided_agent_ids=frozenset(AgentId(value) for value in model.provided_agent_ids),
            required_permissions=decode_permissions(model.required_permissions),
            compatibility=decode_version_range(model.compatibility),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


tool_descriptor_mapper = ToolDescriptorMapper()
agent_descriptor_mapper = AgentDescriptorMapper()
plugin_descriptor_mapper = PluginDescriptorMapper()
