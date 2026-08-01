"""Knowledge — `GET /v1/documents` and `POST /v1/documents` (REST_API_CONTRACT_V1 §3, §4; Slice S4).

Both routes are thin: resolve the tenant (fail-closed), then read the tenant-scoped `document-read-
model` (list) or run the ingestion service (upload). The view groups documents into Evidence
Collections by `evidence_kind` on the client — grouping is presentation, so there is no
`GET /collections`. No chunk / embedding / pgvector detail is ever represented.
"""

from __future__ import annotations

from typing import Annotated

from document_read_model import DocumentReadModel, is_known_kind
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pipeline_contracts import TenantContext

from grc_api.deps import get_document_ingestion, get_document_read_model
from grc_api.document_adapters import DocumentIngestionService
from grc_api.errors import ApiError
from grc_api.schemas import DocumentListResponse, DocumentRow
from grc_api.security import require_tenant

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    read_model: Annotated[DocumentReadModel, Depends(get_document_read_model)],
) -> DocumentListResponse:
    # The tenant's evidence, newest-first. The view groups it into collections client-side.
    return DocumentListResponse.from_items(read_model.list_documents(tenant))


@router.post("/documents", response_model=DocumentRow, status_code=201)
def upload_document(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    ingestion: Annotated[DocumentIngestionService, Depends(get_document_ingestion)],
    evidence_kind: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentRow:
    # Validate the product vocabulary at the boundary: an unknown evidence_kind is a 400, never a
    # silently-mislabelled Document. (Practitioner role is declared in the contract; enforcing it is
    # a deferred cross-cutting concern, like the mission commands.)
    if not is_known_kind(evidence_kind):
        raise ApiError(
            status_code=400,
            code="validation_error",
            message=f"unknown evidence_kind: {evidence_kind!r}",
        )
    # Sync route: read the spooled upload directly. Upload → Ingestion → Document Projection.
    data = file.file.read()
    filename = file.filename or "upload"
    item = ingestion.upload(tenant, filename=filename, evidence_kind=evidence_kind, data=data)
    return DocumentRow.from_item(item)
