"""
Report export service layer.

Orchestrates export job creation, engine selection, data gathering,
file generation, and signed URL creation.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.reports.constants import (
    EXPORT_EXTENSIONS,
    EXPORT_FORMATS_LABEL,
    EXPORT_JOB_TYPES_LABEL,
    EXPORT_MIME_TYPES,
    EXPORT_STORAGE_DIR,
    ExportFormat,
    ExportJobStatus,
)
from app.reports.csv_engine import CSVReportEngine
from app.reports.docx_engine import DOCXReportEngine
from app.reports.json_engine import JSONReportEngine
from app.reports.models import ExportJob
from app.reports.pdf_engine import PDFReportEngine
from app.reports.schemas import (
    ExportJobCreateRequest,
    ExportJobFilterParams,
    ExportJobListResponse,
    ExportJobResponse,
    ExportJobStatusResponse,
    SignedDownloadUrlResponse,
    TemplateConfigSchema,
)
from app.reports.signed_url import SignedUrlGenerator
from app.reports.template_engine import ReportTemplateEngine
from app.reports.xlsx_engine import XLSXReportEngine


class ExportService:
    """
    Export service orchestrating report generation.

    Handles the full lifecycle: job creation -> data preparation ->
    engine dispatch -> file storage -> signed URL generation.
    """

    def __init__(self, db_session: AsyncSession, storage_base: Optional[str] = None):
        self.db = db_session
        self.storage_base = storage_base or os.environ.get(
            "EXPORT_STORAGE_PATH", "/app/storage/exports"
        )
        self.signed_url_gen = SignedUrlGenerator()

    # ------------------------------------------------------------------
    # Job CRUD
    # ------------------------------------------------------------------

    async def create_job(
        self,
        company_id: int,
        user_id: int,
        request: ExportJobCreateRequest,
    ) -> ExportJob:
        """Create a new export job record."""
        template_cfg = None
        if request.template_config:
            template_cfg = request.template_config.model_dump()

        job = ExportJob(
            company_id=company_id,
            branch_id=request.branch_id,
            job_type=request.job_type,
            format=request.format,
            status=ExportJobStatus.PENDING.value,
            report_title=request.report_title,
            report_params=request.report_params or {},
            template_config=template_cfg,
            created_by=user_id,
            retry_count=0,
            max_retries=3,
        )

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_job(self, job_id: int, company_id: int) -> Optional[ExportJob]:
        """Get a single export job by ID and company."""
        result = await self.db.execute(
            select(ExportJob).where(
                ExportJob.id == job_id,
                ExportJob.company_id == company_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        company_id: int,
        filters: ExportJobFilterParams,
    ) -> ExportJobListResponse:
        """List export jobs with filtering and pagination."""
        query = select(ExportJob).where(ExportJob.company_id == company_id)

        if filters.status:
            query = query.where(ExportJob.status == filters.status)
        if filters.job_type:
            query = query.where(ExportJob.job_type == filters.job_type)
        if filters.format:
            query = query.where(ExportJob.format == filters.format)
        if filters.branch_id is not None:
            query = query.where(ExportJob.branch_id == filters.branch_id)

        # Sorting
        sort_col = getattr(ExportJob, filters.sort_by, ExportJob.created_at)
        if filters.sort_order == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(sort_col)

        # Count total
        from sqlalchemy import func as sa_func
        count_result = await self.db.execute(
            select(sa_func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Pagination
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)

        result = await self.db.execute(query)
        jobs = result.scalars().all()

        return ExportJobListResponse(
            items=[self._to_response(j) for j in jobs],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )

    async def get_job_status(self, job_id: int, company_id: int) -> Optional[ExportJobStatusResponse]:
        """Get minimal status for polling."""
        job = await self.get_job(job_id, company_id)
        if job is None:
            return None

        return ExportJobStatusResponse(
            id=job.id,
            status=job.status,
            status_label=self._status_label(job.status),
            progress_percent=self._estimate_progress(job),
            file_size_human=job.file_size_human,
            error_message=job.error_message,
            completed_at=job.completed_at,
        )

    # ------------------------------------------------------------------
    # Job Lifecycle
    # ------------------------------------------------------------------

    async def mark_processing(self, job: ExportJob) -> None:
        """Mark job as processing."""
        job.status = ExportJobStatus.PROCESSING.value
        job.started_at = datetime.utcnow()
        await self.db.commit()

    async def mark_completed(
        self,
        job: ExportJob,
        file_path: str,
        file_size: int,
        file_name: str,
    ) -> None:
        """Mark job as completed with file info."""
        job.status = ExportJobStatus.COMPLETED.value
        job.file_path = file_path
        job.file_size = file_size
        job.file_name = file_name
        job.completed_at = datetime.utcnow()
        job.error_message = None
        await self.db.commit()

    async def mark_failed(self, job: ExportJob, error_message: str) -> None:
        """Mark job as failed."""
        job.status = ExportJobStatus.FAILED.value
        job.error_message = error_message
        job.retry_count += 1
        if job.retry_count >= job.max_retries:
            job.completed_at = datetime.utcnow()
        await self.db.commit()

    async def mark_cancelled(self, job: ExportJob) -> None:
        """Mark job as cancelled."""
        job.status = ExportJobStatus.CANCELLED.value
        job.completed_at = datetime.utcnow()
        await self.db.commit()

    # ------------------------------------------------------------------
    # Signed URL
    # ------------------------------------------------------------------

    async def create_download_url(
        self,
        job: ExportJob,
        base_url: Optional[str] = None,
    ) -> SignedDownloadUrlResponse:
        """Create a signed download URL for a completed export."""
        file_name = job.file_name or f"{job.job_type}_report{EXPORT_EXTENSIONS.get(job.format, '.dat')}"
        mime_type = EXPORT_MIME_TYPES.get(job.format, "application/octet-stream")

        if base_url:
            url, expires = self.signed_url_gen.generate_external_url(
                base_url=base_url,
                file_path=job.file_path or "",
                file_name=file_name,
                mime_type=mime_type,
                company_id=job.company_id,
                user_id=job.created_by,
            )
        else:
            url, expires = self.signed_url_gen.generate(
                file_path=job.file_path or "",
                file_name=file_name,
                mime_type=mime_type,
                company_id=job.company_id,
                user_id=job.created_by,
            )

        return SignedDownloadUrlResponse(
            download_url=url,
            expires_at=expires,
            file_name=file_name,
            file_size_human=job.file_size_human,
            mime_type=mime_type,
        )

    async def verify_download_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a download token and return payload."""
        return self.signed_url_gen.verify(token)

    # ------------------------------------------------------------------
    # File Storage
    # ------------------------------------------------------------------

    def _ensure_storage_dir(self, company_id: int) -> str:
        """Ensure and return the storage directory for a company."""
        dir_path = os.path.join(self.storage_base, str(company_id))
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    def _generate_file_name(self, job: ExportJob) -> str:
        """Generate a unique file name for the export."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique = uuid.uuid4().hex[:8]
        title_part = ""
        if job.report_title:
            title_part = "".join(c if c.isalnum() else "_" for c in job.report_title[:30]) + "_"

        ext = EXPORT_EXTENSIONS.get(job.format, ".dat")
        return f"{job.job_type}_{title_part}{timestamp}_{unique}{ext}"

    # ------------------------------------------------------------------
    # Engine Dispatch
    # ------------------------------------------------------------------

    def get_engine(self, job: ExportJob) -> Any:
        """Get the appropriate engine for the job format."""
        template_cfg = job.template_config or {}

        if job.format == ExportFormat.PDF:
            engine = PDFReportEngine(template_cfg)
        elif job.format == ExportFormat.DOCX:
            engine = DOCXReportEngine(template_cfg)
        elif job.format == ExportFormat.XLSX:
            engine = XLSXReportEngine(template_cfg)
        elif job.format == ExportFormat.CSV:
            engine = CSVReportEngine(template_cfg)
        elif job.format == ExportFormat.JSON:
            engine = JSONReportEngine(template_cfg)
        else:
            raise ValueError(f"Unsupported export format: {job.format}")

        # Set logo if available
        logo_path = None
        if job.template_config and job.template_config.get("logo_path"):
            logo_path = job.template_config["logo_path"]

        if hasattr(engine, "set_logo") and logo_path:
            engine.set_logo(logo_path)

        return engine

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_response(self, job: ExportJob) -> ExportJobResponse:
        """Convert ORM model to response schema."""
        return ExportJobResponse(
            id=job.id,
            company_id=job.company_id,
            branch_id=job.branch_id,
            job_type=job.job_type,
            format=job.format,
            status=job.status,
            file_path=job.file_path,
            file_size=job.file_size,
            file_size_human=job.file_size_human,
            file_name=job.file_name,
            error_message=job.error_message,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            report_title=job.report_title,
            report_params=job.report_params,
            template_config=job.template_config,
            created_by=job.created_by,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            status_label=self._status_label(job.status),
            format_label=EXPORT_FORMATS_LABEL.get(job.format, job.format),
            job_type_label=EXPORT_JOB_TYPES_LABEL.get(job.job_type, job.job_type),
        )

    @staticmethod
    def _status_label(status: str) -> str:
        """Get human-readable status label."""
        return {
            ExportJobStatus.PENDING.value: "Pending",
            ExportJobStatus.PROCESSING.value: "Processing",
            ExportJobStatus.COMPLETED.value: "Completed",
            ExportJobStatus.FAILED.value: "Failed",
            ExportJobStatus.CANCELLED.value: "Cancelled",
        }.get(status, status)

    @staticmethod
    def _estimate_progress(job: ExportJob) -> Optional[int]:
        """Estimate progress percentage for polling."""
        status_progress = {
            ExportJobStatus.PENDING.value: 0,
            ExportJobStatus.PROCESSING.value: 50,
            ExportJobStatus.COMPLETED.value: 100,
            ExportJobStatus.FAILED.value: 0,
            ExportJobStatus.CANCELLED.value: 0,
        }
        return status_progress.get(job.status)

    # ------------------------------------------------------------------
    # Synchronous Generation (called from Celery)
    # ------------------------------------------------------------------

    def generate_file_sync(
        self,
        job: ExportJob,
        report_data: Dict[str, Any],
    ) -> str:
        """
        Synchronously generate the export file.

        This method is called from the Celery worker (sync context).
        Returns the generated file path.
        """
        # Prepare directories
        storage_dir = self._ensure_storage_dir(job.company_id)
        file_name = self._generate_file_name(job)
        output_path = os.path.join(storage_dir, file_name)

        # Build template config
        template_cfg = job.template_config or {}
        template_engine = ReportTemplateEngine(
            company_id=job.company_id,
            custom_config=template_cfg,
        )
        config = template_engine.build_config()

        # Get engine
        engine = self._get_sync_engine(job.format, config)

        # Set logo
        logo_path = template_engine.get_logo_path()
        if logo_path and hasattr(engine, "set_logo"):
            engine.set_logo(logo_path)

        # Extract report data
        title = report_data.get("title", job.report_title or f"{job.job_type} Report")
        subtitle = report_data.get("subtitle")
        sections = report_data.get("sections")
        tables = report_data.get("tables")
        summary_stats = report_data.get("summary_stats")
        headers = report_data.get("headers")
        rows = report_data.get("rows")
        records = report_data.get("records")
        sheets = report_data.get("sheets")

        # Dispatch to engine
        if job.format == ExportFormat.PDF:
            engine.generate(
                output_path=output_path,
                title=title,
                subtitle=subtitle,
                sections=sections,
                tables=tables,
                summary_stats=summary_stats,
            )

        elif job.format == ExportFormat.DOCX:
            engine.generate(
                output_path=output_path,
                title=title,
                subtitle=subtitle,
                sections=sections,
                tables=tables,
                summary_stats=summary_stats,
            )

        elif job.format == ExportFormat.XLSX:
            engine.generate(
                output_path=output_path,
                title=title,
                subtitle=subtitle,
                summary_stats=summary_stats,
                sheets=sheets,
                single_table={"headers": headers, "rows": rows} if headers and rows else None,
            )

        elif job.format == ExportFormat.CSV:
            if records is not None:
                engine.generate_from_dicts(
                    output_path=output_path,
                    records=records,
                )
            else:
                engine.generate(
                    output_path=output_path,
                    title=title,
                    headers=headers or [],
                    rows=rows or [],
                )

        elif job.format == ExportFormat.JSON:
            engine.generate(
                output_path=output_path,
                title=title,
                headers=headers,
                rows=rows,
                records=records,
                metadata=report_data.get("metadata"),
            )

        return output_path

    def _get_sync_engine(self, format: str, config: Dict[str, Any]) -> Any:
        """Get engine instance for sync generation."""
        if format == ExportFormat.PDF:
            return PDFReportEngine(config)
        elif format == ExportFormat.DOCX:
            return DOCXReportEngine(config)
        elif format == ExportFormat.XLSX:
            return XLSXReportEngine(config)
        elif format == ExportFormat.CSV:
            return CSVReportEngine(config)
        elif format == ExportFormat.JSON:
            return JSONReportEngine(config)
        else:
            raise ValueError(f"Unsupported format: {format}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def delete_job(self, job_id: int, company_id: int) -> bool:
        """Delete an export job and its file."""
        job = await self.get_job(job_id, company_id)
        if job is None:
            return False

        # Delete file if exists
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
            except OSError:
                pass

        await self.db.delete(job)
        await self.db.commit()
        return True
