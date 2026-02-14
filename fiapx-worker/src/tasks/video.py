import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pika
import redis
import structlog

from src.core.config import settings
from src.models import Job, JobEvent, JobStatus, SessionLocal
from src.services import FFmpegError, StorageService, VideoProcessor

logger = structlog.get_logger()
redis_client = redis.from_url(settings.redis_url)


def is_duplicate(job_id: str) -> bool:
    """Check if job was already processed."""
    key = f"processed:{job_id}"
    return not redis_client.set(key, "1", nx=True, ex=3600)


def acquire_lock(job_id: str, timeout: int = 1800) -> redis.lock.Lock | None:
    """Acquire distributed lock."""
    lock = redis_client.lock(f"lock:job:{job_id}", timeout=timeout)
    if lock.acquire(blocking=False):
        return lock
    return None


def process_video(job_id: str, video_path: str, retry_count: int = 0) -> dict:
    """Process video: extract frames and create ZIP."""
    logger.info("processing_started", job_id=job_id, attempt=retry_count + 1)

    if is_duplicate(job_id):
        logger.info("duplicate_skipped", job_id=job_id)
        return {"status": "skipped", "reason": "duplicate"}

    lock = acquire_lock(job_id)
    if not lock:
        logger.info("locked_skipped", job_id=job_id)
        return {"status": "skipped", "reason": "locked"}

    db = SessionLocal()
    start_time = time.time()

    try:
        job = db.query(Job).filter(Job.id == UUID(job_id)).first()

        if not job:
            return {"status": "error", "reason": "job_not_found"}

        if job.status in (JobStatus.CANCELLED, JobStatus.DONE):
            return {"status": "skipped", "reason": str(job.status)}

        # Update status to PROCESSING
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        job.retry_count = retry_count
        db.commit()

        _log_event(db, job.id, "PROCESSING_STARTED", JobStatus.QUEUED, JobStatus.PROCESSING)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            local_video = temp_path / f"input{Path(job.video_path).suffix}"
            frames_dir = temp_path / "frames"
            zip_path = temp_path / "output.zip"

            # Download video
            storage = StorageService()
            storage.download_file(job.video_path, str(local_video))

            # Extract frames
            processor = VideoProcessor()
            frames = processor.extract_frames(str(local_video), str(frames_dir))

            if not frames:
                raise FFmpegError("No frames extracted")

            # Create ZIP
            zip_size, frame_count = processor.create_zip(str(frames_dir), str(zip_path))

            # Upload ZIP
            zip_key = f"videos/{job.user_id}/{job.id}/output.zip"
            storage.upload_file(str(zip_path), zip_key)

            processing_time = int(time.time() - start_time)

            # Update job as DONE
            job.status = JobStatus.DONE
            job.zip_path = zip_key
            job.frame_count = frame_count
            job.zip_size_bytes = zip_size
            job.processing_time_seconds = processing_time
            job.completed_at = datetime.now(timezone.utc)
            job.error_code = None
            job.error_message = None
            db.commit()

            _log_event(db, job.id, "PROCESSING_COMPLETED", JobStatus.PROCESSING, JobStatus.DONE,
                      {"frame_count": frame_count, "processing_time": processing_time})

            # Publish notification event
            _publish_notification(job_id, str(job.user_id), "completed")

            logger.info("processing_completed", job_id=job_id, frame_count=frame_count)

            return {
                "status": "success",
                "job_id": job_id,
                "frame_count": frame_count,
                "zip_size_bytes": zip_size,
            }

    except (FFmpegError, Exception) as e:
        error_code = "FFMPEG_ERROR" if isinstance(e, FFmpegError) else "PROCESSING_ERROR"
        logger.error("processing_failed", job_id=job_id, error=str(e))

        job = db.query(Job).filter(Job.id == UUID(job_id)).first()
        if job:
            job.error_code = error_code
            job.error_message = str(e)[:500]

            if retry_count >= settings.max_retries - 1:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                _log_event(db, job.id, "PROCESSING_FAILED", JobStatus.PROCESSING, JobStatus.FAILED)
                _publish_notification(job_id, str(job.user_id), "failed")

            db.commit()

        return {"status": "failed", "error": str(e), "retry": retry_count < settings.max_retries - 1}

    finally:
        if lock:
            try:
                lock.release()
            except redis.exceptions.LockError:
                pass
        db.close()


def _log_event(db, job_id: UUID, event_type: str, old_status, new_status, metadata=None):
    event = JobEvent(
        job_id=job_id,
        event_type=event_type,
        old_status=old_status,
        new_status=new_status,
        metadata=metadata,
    )
    db.add(event)
    db.commit()


def _publish_notification(job_id: str, user_id: str, notification_type: str):
    """Publish notification event to RabbitMQ."""
    try:
        params = pika.URLParameters(settings.rabbitmq_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        channel.queue_declare(queue="notification.send", durable=True)

        message = {
            "job_id": job_id,
            "user_id": user_id,
            "type": notification_type,
        }

        channel.basic_publish(
            exchange="",
            routing_key="notification.send",
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),
        )

        connection.close()
        logger.info("notification_published", job_id=job_id, type=notification_type)

    except Exception as e:
        logger.error("notification_publish_failed", job_id=job_id, error=str(e))
