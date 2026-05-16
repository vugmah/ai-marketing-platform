"""
Celery tasks for async report export processing.

Background tasks that handle the full export lifecycle:
processing -> generation -> completion notification.
"""

import json
import os
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

from app.reports.constants import (
    EXPORT_EXTENSIONS,
    ExportFormat,
    ExportJobStatus,
    MAX_EXPORT_FILE_SIZE_MB,
)

# ---------------------------------------------------------------------------
# DB Helper (runs in sync Celery context)
# ---------------------------------------------------------------------------

def _get_sync_session():
    """Create a sync DB session for Celery worker context."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ.get("DATABASE_URL", "mysql+pymysql://user:pass@localhost/db")
    engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)
    Session = sessionmaker(bind=engine)
    return Session()


def _update_job_status(
    job_id: int,
    status: str,
    file_path: Optional[str] = None,
    file_size: Optional[int] = None,
    file_name: Optional[str] = None,
    error_message: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    retry_count: Optional[int] = None,
) -> None:
    """Update export job status in DB from Celery context."""
    session = _get_sync_session()
    try:
        from app.reports.models import ExportJob

        job = session.query(ExportJob).filter(ExportJob.id == job_id).first()
        if job is None:
            return

        job.status = status
        if file_path is not None:
            job.file_path = file_path
        if file_size is not None:
            job.file_size = file_size
        if file_name is not None:
            job.file_name = file_name
        if error_message is not None:
            job.error_message = error_message
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        if retry_count is not None:
            job.retry_count = retry_count

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _fetch_job(job_id: int):
    """Fetch export job from DB."""
    session = _get_sync_session()
    try:
        from app.reports.models import ExportJob

        return session.query(ExportJob).filter(ExportJob.id == job_id).first()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Main Export Task
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    time_limit=1800,  # 30 min
    soft_time_limit=1500,  # 25 min
    queue="reports",
    name="app.reports.tasks.process_export_job",
)
def process_export_job(self, job_id: int, report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process an export job asynchronously.

    Workflow:
        1. Load job from DB
        2. Mark as processing
        3. Generate file using appropriate engine
        4. Mark as completed or failed
        5. Return result metadata

    Args:
        job_id: Export job ID.
        report_data: Report content data dict.

    Returns:
        Dict with file_path, file_size, file_name, status.
    """
    # Fetch job
    job = _fetch_job(job_id)
    if job is None:
        return {"status": "failed", "error": f"Export job {job_id} not found"}

    if job.is_terminal:
        return {"status": "skipped", "reason": "Job already in terminal state"}

    try:
        # Mark processing
        _update_job_status(
            job_id=job_id,
            status=ExportJobStatus.PROCESSING.value,
            started_at=datetime.utcnow(),
        )

        # Generate file
        from app.reports.service import ExportService

        # Create service with sync session
        service = ExportService.__new__(ExportService)
        service.storage_base = os.environ.get("EXPORT_STORAGE_PATH", "/app/storage/exports")
        service.signed_url_gen = None  # Not needed in task

        output_path = service.generate_file_sync(job, report_data)

        # Check file size
        file_size = os.path.getsize(output_path)
        max_size = MAX_EXPORT_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            os.remove(output_path)
            raise ValueError(f"Generated file exceeds {MAX_EXPORT_FILE_SIZE_MB}MB limit")

        file_name = os.path.basename(output_path)

        # Mark completed
        _update_job_status(
            job_id=job_id,
            status=ExportJobStatus.COMPLETED.value,
            file_path=output_path,
            file_size=file_size,
            file_name=file_name,
            completed_at=datetime.utcnow(),
            error_message=None,
        )

        return {
            "status": "completed",
            "job_id": job_id,
            "file_path": output_path,
            "file_size": file_size,
            "file_name": file_name,
        }

    except SoftTimeLimitExceeded:
        _update_job_status(
            job_id=job_id,
            status=ExportJobStatus.FAILED.value,
            error_message="Export timed out (soft time limit exceeded)",
            completed_at=datetime.utcnow(),
        )
        raise

    except Exception as exc:
        error_msg = f"{str(exc)}\n{traceback.format_exc()[:500]}"
        current_retry = (job.retry_count or 0) + 1

        if current_retry < job.max_retries:
            _update_job_status(
                job_id=job_id,
                status=ExportJobStatus.PENDING.value,
                error_message=error_msg,
                retry_count=current_retry,
            )
            # Retry with exponential backoff
            retry_delay = 10 * (2 ** current_retry)
            raise self.retry(exc=exc, countdown=min(retry_delay, 300))
        else:
            _update_job_status(
                job_id=job_id,
                status=ExportJobStatus.FAILED.value,
                error_message=f"Max retries exceeded. Last error: {error_msg[:500]}",
                retry_count=current_retry,
                completed_at=datetime.utcnow(),
            )

        return {
            "status": "failed",
            "job_id": job_id,
            "error": error_msg[:500],
        }


# ---------------------------------------------------------------------------
# Cleanup Task
# ---------------------------------------------------------------------------

@shared_task(
    queue="reports",
    name="app.reports.tasks.cleanup_old_exports",
)
def cleanup_old_exports(older_than_days: int = 7) -> Dict[str, int]:
    """
    Clean up expired export files and old completed jobs.

    Args:
        older_than_days: Delete exports older than this many days.

    Returns:
        Dict with files_deleted and jobs_cleaned counts.
    """
    session = _get_sync_session()
    try:
        from sqlalchemy import delete, func
        from app.reports.models import ExportJob
        from app.reports.constants import ExportJobStatus, EXPORT_CLEANUP_DAYS

        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)

        # Find old completed/failed jobs
        old_jobs = (
            session.query(ExportJob)
            .filter(
                ExportJob.completed_at < cutoff,
                ExportJob.status.in_([
                    ExportJobStatus.COMPLETED.value,
                    ExportJobStatus.FAILED.value,
                    ExportJobStatus.CANCELLED.value,
                ]),
            )
            .all()
        )

        files_deleted = 0
        jobs_cleaned = 0

        for job in old_jobs:
            # Delete file
            if job.file_path and os.path.exists(job.file_path):
                try:
                    os.remove(job.file_path)
                    files_deleted += 1
                except OSError:
                    pass

            # Delete job record
            session.delete(job)
            jobs_cleaned += 1

        session.commit()

        return {
            "files_deleted": files_deleted,
            "jobs_cleaned": jobs_cleaned,
        }

    except Exception as exc:
        session.rollback()
        return {"files_deleted": 0, "jobs_cleaned": 0, "error": str(exc)}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Retry Failed Jobs Task
# ---------------------------------------------------------------------------

@shared_task(
    queue="reports",
    name="app.reports.tasks.retry_failed_exports",
)
def retry_failed_exports(max_age_hours: int = 24) -> Dict[str, int]:
    """
    Re-queue failed export jobs that haven't exceeded max retries.

    Args:
        max_age_hours: Only retry jobs failed within this window.

    Returns:
        Dict with retried_count.
    """
    session = _get_sync_session()
    try:
        from app.reports.models import ExportJob
        from app.reports.constants import ExportJobStatus

        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        failed_jobs = (
            session.query(ExportJob)
            .filter(
                ExportJob.status == ExportJobStatus.FAILED.value,
                ExportJob.created_at > cutoff,
                ExportJob.retry_count < ExportJob.max_retries,
            )
            .all()
        )

        retried = 0
        for job in failed_jobs:
            job.status = ExportJobStatus.PENDING.value
            job.error_message = None
            retried += 1

        session.commit()

        # Re-queue tasks
        for job in failed_jobs:
            # Trigger reprocessing
            process_export_job.delay(job.id, job.report_params or {})

        return {"retried_count": retried}

    except Exception as exc:
        session.rollback()
        return {"retried_count": 0, "error": str(exc)}
    finally:
        session.close()
