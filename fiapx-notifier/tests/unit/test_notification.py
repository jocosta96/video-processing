"""
Unit tests for src/tasks/notification.py

Tests email notification sending and template generation.
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672"
os.environ["SMTP_HOST"] = "localhost"
os.environ["SMTP_PORT"] = "1025"
os.environ["EMAIL_FROM"] = "test@fiapx.com"

from src.tasks.notification import (
    _completed_body,
    _failed_body,
    send_notification,
)


class TestEmailBodyGeneration:
    """Tests for email body generation functions."""

    @pytest.fixture
    def mock_completed_job(self):
        """Create a mock completed job."""
        job = MagicMock()
        job.original_filename = "my_video.mp4"
        job.frame_count = 120
        job.processing_time_seconds = 45
        return job

    @pytest.fixture
    def mock_failed_job(self):
        """Create a mock failed job."""
        job = MagicMock()
        job.original_filename = "problem_video.mp4"
        job.error_message = "Unsupported codec: hevc"
        return job

    @pytest.mark.unit
    def test_completed_body_contains_user_name(self, mock_completed_job):
        """Completed email should address user by name."""
        body = _completed_body("John Doe", mock_completed_job)

        assert "John Doe" in body

    @pytest.mark.unit
    def test_completed_body_contains_filename(self, mock_completed_job):
        """Completed email should include the video filename."""
        body = _completed_body("Test User", mock_completed_job)

        assert "my_video.mp4" in body

    @pytest.mark.unit
    def test_completed_body_contains_frame_count(self, mock_completed_job):
        """Completed email should include frame count."""
        body = _completed_body("Test User", mock_completed_job)

        assert "120" in body

    @pytest.mark.unit
    def test_completed_body_contains_processing_time(self, mock_completed_job):
        """Completed email should include processing time."""
        body = _completed_body("Test User", mock_completed_job)

        assert "45" in body

    @pytest.mark.unit
    def test_completed_body_has_positive_message(self, mock_completed_job):
        """Completed email should have positive messaging."""
        body = _completed_body("Test User", mock_completed_job)

        assert "success" in body.lower() or "great" in body.lower()

    @pytest.mark.unit
    def test_failed_body_contains_user_name(self, mock_failed_job):
        """Failed email should address user by name."""
        body = _failed_body("Jane Doe", mock_failed_job)

        assert "Jane Doe" in body

    @pytest.mark.unit
    def test_failed_body_contains_filename(self, mock_failed_job):
        """Failed email should include the video filename."""
        body = _failed_body("Test User", mock_failed_job)

        assert "problem_video.mp4" in body

    @pytest.mark.unit
    def test_failed_body_contains_error_message(self, mock_failed_job):
        """Failed email should include error message."""
        body = _failed_body("Test User", mock_failed_job)

        assert "Unsupported codec: hevc" in body

    @pytest.mark.unit
    def test_failed_body_handles_none_error_message(self):
        """Failed email should handle None error message."""
        job = MagicMock()
        job.original_filename = "video.mp4"
        job.error_message = None

        body = _failed_body("Test User", job)

        assert "Unknown error" in body

    @pytest.mark.unit
    def test_failed_body_has_apologetic_message(self, mock_failed_job):
        """Failed email should have apologetic messaging."""
        body = _failed_body("Test User", mock_failed_job)

        assert "error" in body.lower() or "unfortunately" in body.lower()


class TestSendNotification:
    """Tests for send_notification function."""

    @pytest.mark.unit
    def test_send_notification_returns_error_for_missing_job(self):
        """Should return error when job not found."""
        job_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with patch("src.tasks.notification.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value = mock_db

            result = send_notification(job_id, user_id, "completed")

            assert result["status"] == "error"
            assert result["reason"] == "not_found"

    @pytest.mark.unit
    def test_send_notification_returns_error_for_missing_user(self):
        """Should return error when user not found."""
        job_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with patch("src.tasks.notification.SessionLocal") as mock_session:
            mock_db = MagicMock()
            # Job exists, user doesn't
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                MagicMock(),  # Job
                None,  # User
            ]
            mock_session.return_value = mock_db

            result = send_notification(job_id, user_id, "completed")

            assert result["status"] == "error"
            assert result["reason"] == "not_found"

    @pytest.mark.unit
    def test_send_notification_completed_success(self):
        """Should successfully send completed notification."""
        job_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_job = MagicMock()
        mock_job.original_filename = "video.mp4"
        mock_job.frame_count = 60
        mock_job.processing_time_seconds = 30

        mock_user = MagicMock()
        mock_user.name = "Test User"
        mock_user.email = "test@example.com"

        with patch("src.tasks.notification.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                mock_job,
                mock_user,
            ]
            mock_session.return_value = mock_db

            with patch("src.tasks.notification._send_email") as mock_send:
                result = send_notification(job_id, user_id, "completed")

                assert result["status"] == "success"
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                assert call_args[0][0] == "test@example.com"
                assert "ready" in call_args[0][1].lower()

    @pytest.mark.unit
    def test_send_notification_failed_success(self):
        """Should successfully send failed notification."""
        job_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_job = MagicMock()
        mock_job.original_filename = "video.mp4"
        mock_job.error_message = "Processing error"

        mock_user = MagicMock()
        mock_user.name = "Test User"
        mock_user.email = "test@example.com"

        with patch("src.tasks.notification.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                mock_job,
                mock_user,
            ]
            mock_session.return_value = mock_db

            with patch("src.tasks.notification._send_email") as mock_send:
                result = send_notification(job_id, user_id, "failed")

                assert result["status"] == "success"
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                assert "error" in call_args[0][1].lower()

    @pytest.mark.unit
    def test_send_notification_handles_smtp_error(self):
        """Should return error when SMTP fails."""
        job_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_job = MagicMock()
        mock_job.original_filename = "video.mp4"
        mock_job.frame_count = 60
        mock_job.processing_time_seconds = 30

        mock_user = MagicMock()
        mock_user.name = "Test User"
        mock_user.email = "test@example.com"

        with patch("src.tasks.notification.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                mock_job,
                mock_user,
            ]
            mock_session.return_value = mock_db

            with patch("src.tasks.notification._send_email") as mock_send:
                mock_send.side_effect = Exception("SMTP connection failed")

                result = send_notification(job_id, user_id, "completed")

                assert result["status"] == "error"
                assert "SMTP" in result["error"]


class TestEmailSending:
    """Tests for _send_email function."""

    @pytest.mark.unit
    def test_send_email_creates_multipart_message(self):
        """Email should be multipart with plain and HTML."""
        from src.tasks.notification import _send_email

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            _send_email("test@example.com", "Test Subject", "Test body")

            mock_server.sendmail.assert_called_once()
            call_args = mock_server.sendmail.call_args[0]

            # Check from address
            assert call_args[0] == "test@fiapx.com"
            # Check to address
            assert call_args[1] == "test@example.com"
            # Check message contains both parts
            message = call_args[2]
            assert "Test Subject" in message
            assert "Test body" in message

    @pytest.mark.unit
    def test_send_email_uses_correct_smtp_settings(self):
        """Email should use configured SMTP settings."""
        from src.tasks.notification import _send_email

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            _send_email("test@example.com", "Subject", "Body")

            mock_smtp.assert_called_once_with("localhost", 1025)
