from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.models.job import JobStatus


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: JobStatus
    video_format: str
    video_size_bytes: int
    original_filename: str
    frame_count: int | None = None
    zip_size_bytes: int | None = None
    processing_time_seconds: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    download_available: bool = False

    @classmethod
    def from_job(cls, job) -> "JobResponse":
        return cls(
            id=job.id,
            status=job.status,
            video_format=job.video_format,
            video_size_bytes=job.video_size_bytes,
            original_filename=job.original_filename,
            frame_count=job.frame_count,
            zip_size_bytes=job.zip_size_bytes,
            processing_time_seconds=job.processing_time_seconds,
            error_code=job.error_code,
            error_message=job.error_message,
            retry_count=job.retry_count,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            expires_at=job.expires_at,
            download_available=job.status == JobStatus.DONE and job.zip_path is not None,
        )


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int


class JobStatusResponse(BaseModel):
    id: UUID
    status: JobStatus
    progress: str | None = None
    message: str | None = None


class DownloadResponse(BaseModel):
    download_url: str
    expires_in: int
    filename: str


class UploadResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    message: str
