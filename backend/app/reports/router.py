"""
FastAPI router for report export API.

Endpoints: create export, list jobs, get status, download file,
cancel job, delete job, preview template.
"""

import os
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.reports.constants import (
    EXPORT_EXTENSIONS,
    EXPORT_MIME_TYPES,
    ExportFormat,
    ExportJobStatus,
)
from app.reports.schemas import (
    ExportJobCreateRequest,
    ExportJobFilterParams,
    ExportJobListResponse,
    ExportJobResponse,
    ExportJobStatusResponse,
    SignedDownloadUrlResponse,
    TemplatePreviewResponse,
)
from app.reports.service import ExportService
from app.reports.tasks import process_export_job

router = APIRouter(prefix="/reports", tags=["Reports"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_export_service(db: AsyncSession = Depends(get_db)) -> ExportService:
    """Dependency to get export service with DB session."""
    return ExportService(db_session=db)


# ---------------------------------------------------------------------------
# Create Export
# ---------------------------------------------------------------------------

@router.post(
    "/exports",
    response_model=ExportJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new async export job",
)
async def create_export(
    request: Request,
    body: ExportJobCreateRequest,
    background_tasks: BackgroundTasks,
    service: ExportService = Depends(get_export_service),
):
    """
    Create a new async report export job.

    The job is queued via Celery and processed asynchronously.
    Poll GET /exports/{id}/status to check progress.
    """
    # Extract company/user from auth context (placeholder)
    company_id = _extract_company_id(request)
    user_id = _extract_user_id(request)

    # Validate report data in params
    report_data = body.report_params or {}
    if not any(k in report_data for k in ("tables", "sections", "rows", "records", "sheets")):
        if not body.report_title:
            pass  # Allow empty for now

    # Create job
    job = await service.create_job(company_id, user_id, body)

    # Dispatch Celery task
    process_export_job.delay(job.id, report_data)

    return service._to_response(job)


# ---------------------------------------------------------------------------
# List Exports
# ---------------------------------------------------------------------------

@router.get(
    "/exports",
    response_model=ExportJobListResponse,
    summary="List export jobs with filtering",
)
async def list_exports(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    format: Optional[str] = Query(None, description="Filter by format"),
    branch_id: Optional[int] = Query(None, description="Filter by branch"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", pattern=r"^(created_at|completed_at|status)$"),
    sort_order: str = Query("desc", pattern=r"^(asc|desc)$"),
    service: ExportService = Depends(get_export_service),
):
    """List export jobs with pagination and filtering."""
    company_id = _extract_company_id(request)

    filters = ExportJobFilterParams(
        status=status,
        job_type=job_type,
        format=format,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return await service.list_jobs(company_id, filters)


# ---------------------------------------------------------------------------
# Get Job
# ---------------------------------------------------------------------------

@router.get(
    "/exports/{job_id}",
    response_model=ExportJobResponse,
    summary="Get export job details",
)
async def get_export(
    job_id: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    """Get detailed information about a specific export job."""
    company_id = _extract_company_id(request)
    job = await service.get_job(job_id, company_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    return service._to_response(job)


# ---------------------------------------------------------------------------
# Get Job Status (Polling)
# ---------------------------------------------------------------------------

@router.get(
    "/exports/{job_id}/status",
    response_model=ExportJobStatusResponse,
    summary="Get export job status for polling",
)
async def get_export_status(
    job_id: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    """
    Get minimal status for frontend polling.

    Returns progress percentage and completion state.
    """
    company_id = _extract_company_id(request)
    status_resp = await service.get_job_status(job_id, company_id)
    if status_resp is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    return status_resp


# ---------------------------------------------------------------------------
# Get Download URL
# ---------------------------------------------------------------------------

@router.get(
    "/exports/{job_id}/download",
    response_model=SignedDownloadUrlResponse,
    summary="Get signed download URL",
)
async def get_download_url(
    job_id: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    """
    Generate a time-limited signed download URL.

    The URL expires after 1 hour. Call again for a fresh URL.
    """
    company_id = _extract_company_id(request)
    job = await service.get_job(job_id, company_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.status != ExportJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Export not ready (status: {job.status})",
        )

    base_url = str(request.base_url).rstrip("/")
    return await service.create_download_url(job, base_url=base_url)


# ---------------------------------------------------------------------------
# Direct Download
# ---------------------------------------------------------------------------

@router.get(
    "/exports/download",
    summary="Download exported file (signed URL endpoint)",
)
async def download_file(
    token: str = Query(..., description="Signed download token"),
    service: ExportService = Depends(get_export_service),
):
    """
    Download an exported file using a signed token.

    Validates the token and serves the file.
    """
    payload = await service.verify_download_token(token)
    if payload is None:
        raise HTTPException(status_code=403, detail="Invalid or expired download token")

    file_path = payload.get("sub")
    file_name = payload.get("fn")
    mime_type = payload.get("mime", "application/octet-stream")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type=mime_type,
    )


# ---------------------------------------------------------------------------
# Cancel Job
# ---------------------------------------------------------------------------

@router.post(
    "/exports/{job_id}/cancel",
    response_model=ExportJobStatusResponse,
    summary="Cancel a pending export job",
)
async def cancel_export(
    job_id: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    """Cancel a pending or processing export job."""
    company_id = _extract_company_id(request)
    job = await service.get_job(job_id, company_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.is_terminal:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in '{job.status}' state",
        )

    await service.mark_cancelled(job)
    return await service.get_job_status(job_id, company_id)


# ---------------------------------------------------------------------------
# Delete Job
# ---------------------------------------------------------------------------

@router.delete(
    "/exports/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an export job and its file",
)
async def delete_export(
    job_id: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    """Delete an export job and its associated file."""
    company_id = _extract_company_id(request)
    deleted = await service.delete_job(job_id, company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Export job not found")
    return None


# ---------------------------------------------------------------------------
# Preview Template
# ---------------------------------------------------------------------------

@router.get(
    "/template-preview",
    response_model=TemplatePreviewResponse,
    summary="Preview company template configuration",
)
async def preview_template(
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    """Preview the template configuration for the current company."""
    company_id = _extract_company_id(request)

    from app.reports.template_engine import ReportTemplateEngine

    template_engine = ReportTemplateEngine(company_id=company_id)
    config = template_engine.build_config()

    logo_path = template_engine.get_logo_path()

    return TemplatePreviewResponse(
        primary_color=config.get("primary_color", "#2563EB"),
        secondary_color=config.get("secondary_color", "#1E40AF"),
        font_family=config.get("font_family", "Helvetica"),
        page_size=config.get("page_size", "A4"),
        orientation=config.get("orientation", "portrait"),
        logo_available=logo_path is not None,
        sample_header=f"Report for Company {company_id}",
        sample_footer=config.get("footer_text", "Generated by Report Engine"),
    )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    summary="Export engine health check",
)
async def health_check():
    """Quick health check for the export engine."""
    return {
        "status": "ok",
        "engines": {
            "pdf": "reportlab",
            "docx": "python-docx",
            "xlsx": "openpyxl",
            "csv": "pandas",
            "json": "native",
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_company_id(request: Request) -> int:
    """Extract company ID from request state/auth."""
    company_id = getattr(request.state, "company_id", None)
    if company_id is None:
        # Fallback for dev/testing - extract from header
        company_id = request.headers.get("X-Company-ID", "1")
    return int(company_id)


def _extract_user_id(request: Request) -> int:
    """Extract user ID from request state/auth."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        user_id = request.headers.get("X-User-ID", "1")
    return int(user_id)
