"""
Shared fixtures for fiapx-notifier tests.

The notifier service has a simplified data model - it only needs to look up
user/job info, not perform status transitions.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker

# Set test environment before imports
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672"
os.environ["SMTP_HOST"] = "localhost"
os.environ["SMTP_PORT"] = "1025"
os.environ["EMAIL_FROM"] = "test@fiapx.com"


fake = Faker()


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_smtp():
    """Mock SMTP for email sending tests."""
    with patch("smtplib.SMTP") as mock:
        smtp_instance = MagicMock()
        mock.return_value.__enter__ = MagicMock(return_value=smtp_instance)
        mock.return_value.__exit__ = MagicMock(return_value=False)
        yield smtp_instance


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_user_data() -> dict:
    """Test user data for notification context."""
    return {
        "id": str(uuid.uuid4()),
        "email": fake.email(),
        "name": fake.name(),
    }


@pytest.fixture
def completed_job_data(test_user_data) -> dict:
    """Test completed job data for notification context."""
    return {
        "job_id": str(uuid.uuid4()),
        "user_id": test_user_data["id"],
        "user_email": test_user_data["email"],
        "user_name": test_user_data["name"],
        "original_filename": "test_video.mp4",
        "frame_count": 60,
        "processing_time_seconds": 30,
        "status": "DONE",
    }


@pytest.fixture
def failed_job_data(test_user_data) -> dict:
    """Test failed job data for notification context."""
    return {
        "job_id": str(uuid.uuid4()),
        "user_id": test_user_data["id"],
        "user_email": test_user_data["email"],
        "user_name": test_user_data["name"],
        "original_filename": "test_video.mp4",
        "error_message": "Unsupported codec: hevc",
        "status": "FAILED",
    }
