"""
Unit tests for src/tasks/video.py

Tests video processing task logic, deduplication, and locking.
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672"
os.environ["MINIO_ENDPOINT"] = "http://localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "minioadmin"
os.environ["MINIO_SECRET_KEY"] = "minioadmin"
os.environ["MINIO_BUCKET"] = "test-bucket"

from src.tasks.video import is_duplicate, acquire_lock


class TestDeduplication:
    """Tests for job deduplication."""

    @pytest.mark.unit
    def test_is_duplicate_returns_false_for_new_job(self):
        """New job should not be marked as duplicate."""
        job_id = str(uuid.uuid4())

        with patch("src.tasks.video.redis_client") as mock_redis:
            # SETNX returns True for new keys
            mock_redis.set.return_value = True

            result = is_duplicate(job_id)

            assert result is False
            mock_redis.set.assert_called_once_with(
                f"processed:{job_id}", "1", nx=True, ex=3600
            )

    @pytest.mark.unit
    def test_is_duplicate_returns_true_for_existing_job(self):
        """Already processed job should be marked as duplicate."""
        job_id = str(uuid.uuid4())

        with patch("src.tasks.video.redis_client") as mock_redis:
            # SETNX returns False for existing keys
            mock_redis.set.return_value = False

            result = is_duplicate(job_id)

            assert result is True


class TestLocking:
    """Tests for distributed locking."""

    @pytest.mark.unit
    def test_acquire_lock_success(self):
        """Lock should be acquired successfully."""
        job_id = str(uuid.uuid4())

        with patch("src.tasks.video.redis_client") as mock_redis:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_redis.lock.return_value = mock_lock

            lock = acquire_lock(job_id)

            assert lock is not None
            mock_redis.lock.assert_called_once_with(
                f"lock:job:{job_id}", timeout=1800
            )

    @pytest.mark.unit
    def test_acquire_lock_failure(self):
        """Lock acquisition should return None when lock is held."""
        job_id = str(uuid.uuid4())

        with patch("src.tasks.video.redis_client") as mock_redis:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = False
            mock_redis.lock.return_value = mock_lock

            lock = acquire_lock(job_id)

            assert lock is None

    @pytest.mark.unit
    def test_acquire_lock_with_custom_timeout(self):
        """Lock should use custom timeout."""
        job_id = str(uuid.uuid4())
        custom_timeout = 3600

        with patch("src.tasks.video.redis_client") as mock_redis:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_redis.lock.return_value = mock_lock

            acquire_lock(job_id, timeout=custom_timeout)

            mock_redis.lock.assert_called_once_with(
                f"lock:job:{job_id}", timeout=custom_timeout
            )


class TestProcessVideo:
    """Tests for process_video function."""

    @pytest.mark.unit
    def test_process_video_skips_duplicate(self):
        """Duplicate jobs should be skipped."""
        from src.tasks.video import process_video

        job_id = str(uuid.uuid4())
        video_path = "videos/user/job/input.mp4"

        with patch("src.tasks.video.is_duplicate", return_value=True):
            result = process_video(job_id, video_path)

            assert result["status"] == "skipped"
            assert result["reason"] == "duplicate"

    @pytest.mark.unit
    def test_process_video_skips_locked(self):
        """Locked jobs should be skipped."""
        from src.tasks.video import process_video

        job_id = str(uuid.uuid4())
        video_path = "videos/user/job/input.mp4"

        with patch("src.tasks.video.is_duplicate", return_value=False):
            with patch("src.tasks.video.acquire_lock", return_value=None):
                result = process_video(job_id, video_path)

                assert result["status"] == "skipped"
                assert result["reason"] == "locked"

    @pytest.mark.unit
    def test_process_video_returns_error_for_missing_job(self):
        """Missing job should return error."""
        from src.tasks.video import process_video

        job_id = str(uuid.uuid4())
        video_path = "videos/user/job/input.mp4"

        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True

        with patch("src.tasks.video.is_duplicate", return_value=False):
            with patch("src.tasks.video.acquire_lock", return_value=mock_lock):
                with patch("src.tasks.video.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_db.query.return_value.filter.return_value.first.return_value = None
                    mock_session.return_value = mock_db

                    result = process_video(job_id, video_path)

                    assert result["status"] == "error"
                    assert result["reason"] == "job_not_found"


class TestProcessVideoStatusTransitions:
    """Tests for job status transitions during processing."""

    @pytest.fixture
    def mock_job(self):
        """Create a mock job object."""
        from src.models.job import JobStatus

        job = MagicMock()
        job.id = uuid.uuid4()
        job.user_id = uuid.uuid4()
        job.status = JobStatus.QUEUED
        job.video_path = "videos/user/job/input.mp4"
        return job

    @pytest.mark.unit
    def test_skips_cancelled_job(self, mock_job):
        """Cancelled jobs should be skipped."""
        from src.models.job import JobStatus
        from src.tasks.video import process_video

        mock_job.status = JobStatus.CANCELLED
        job_id = str(mock_job.id)
        video_path = mock_job.video_path

        mock_lock = MagicMock()

        with patch("src.tasks.video.is_duplicate", return_value=False):
            with patch("src.tasks.video.acquire_lock", return_value=mock_lock):
                with patch("src.tasks.video.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_db.query.return_value.filter.return_value.first.return_value = mock_job
                    mock_session.return_value = mock_db

                    result = process_video(job_id, video_path)

                    assert result["status"] == "skipped"
                    assert "CANCELLED" in result["reason"]

    @pytest.mark.unit
    def test_skips_already_done_job(self, mock_job):
        """Already completed jobs should be skipped."""
        from src.models.job import JobStatus
        from src.tasks.video import process_video

        mock_job.status = JobStatus.DONE
        job_id = str(mock_job.id)
        video_path = mock_job.video_path

        mock_lock = MagicMock()

        with patch("src.tasks.video.is_duplicate", return_value=False):
            with patch("src.tasks.video.acquire_lock", return_value=mock_lock):
                with patch("src.tasks.video.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_db.query.return_value.filter.return_value.first.return_value = mock_job
                    mock_session.return_value = mock_db

                    result = process_video(job_id, video_path)

                    assert result["status"] == "skipped"
                    assert "DONE" in result["reason"]
