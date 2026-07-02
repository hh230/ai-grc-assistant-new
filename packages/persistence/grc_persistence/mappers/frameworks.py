"""Mappers for the Frameworks context."""

from __future__ import annotations

from grc_domain.frameworks.entities import Framework, FrameworkMappingSet
from grc_domain.frameworks.enums import FrameworkStatus
from grc_domain.frameworks.value_objects import FrameworkVersion
from grc_domain.shared.identifiers import FrameworkId, FrameworkMappingId

from ..contracts.mapper import AggregateMapper
from ..models.frameworks import FrameworkMappingSetModel, FrameworkModel
from ._common import (
    aware,
    decode_correspondence,
    decode_framework_control,
    encode_correspondence,
    encode_framework_control,
)


class FrameworkMapper(AggregateMapper[Framework, FrameworkModel]):
    def to_orm(self, aggregate: Framework) -> FrameworkModel:
        return FrameworkModel(
            id=str(aggregate.id),
            version_label=str(aggregate.version),
            name=aggregate.name,
            region=aggregate.region,
            languages=list(aggregate.languages),
            status=aggregate.status.value,
            controls=[encode_framework_control(control) for control in aggregate.controls],
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: FrameworkModel, aggregate: Framework) -> None:
        model.name = aggregate.name
        model.region = aggregate.region
        model.languages = list(aggregate.languages)
        model.status = aggregate.status.value
        model.controls = [encode_framework_control(control) for control in aggregate.controls]
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: FrameworkModel) -> Framework:
        return Framework(
            id=FrameworkId(model.id),
            name=model.name,
            version=FrameworkVersion(model.version_label),
            region=model.region,
            languages=tuple(model.languages),
            status=FrameworkStatus(model.status),
            controls=tuple(decode_framework_control(item) for item in model.controls),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


class FrameworkMappingSetMapper(AggregateMapper[FrameworkMappingSet, FrameworkMappingSetModel]):
    def to_orm(self, aggregate: FrameworkMappingSet) -> FrameworkMappingSetModel:
        return FrameworkMappingSetModel(
            id=str(aggregate.id),
            source_framework_id=str(aggregate.source_framework_id),
            target_framework_id=str(aggregate.target_framework_id),
            correspondences=[encode_correspondence(item) for item in aggregate.correspondences],
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: FrameworkMappingSetModel, aggregate: FrameworkMappingSet) -> None:
        model.source_framework_id = str(aggregate.source_framework_id)
        model.target_framework_id = str(aggregate.target_framework_id)
        model.correspondences = [encode_correspondence(item) for item in aggregate.correspondences]
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: FrameworkMappingSetModel) -> FrameworkMappingSet:
        return FrameworkMappingSet(
            id=FrameworkMappingId(model.id),
            source_framework_id=FrameworkId(model.source_framework_id),
            target_framework_id=FrameworkId(model.target_framework_id),
            correspondences=tuple(decode_correspondence(item) for item in model.correspondences),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


framework_mapper = FrameworkMapper()
framework_mapping_set_mapper = FrameworkMappingSetMapper()
