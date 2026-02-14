"""
Unit tests for src/api/schemas/

Tests Pydantic schema validation, especially password requirements.
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.api.schemas.auth import RefreshTokenRequest, TokenResponse, UserCreate, UserLogin, UserResponse
from src.api.schemas.job import DownloadResponse, JobResponse, JobStatusResponse, UploadResponse
from src.models.job import JobStatus


class TestUserCreate:
    """Tests for UserCreate schema validation."""

    @pytest.mark.unit
    def test_valid_user_create(self):
        """Valid data should create UserCreate successfully."""
        user = UserCreate(
            email="test@example.com",
            password="SecureP@ss123",
            name="Test User",
        )
        assert user.email == "test@example.com"
        assert user.password == "SecureP@ss123"
        assert user.name == "Test User"

    @pytest.mark.unit
    def test_password_too_short(self):
        """Password with less than 8 characters should fail."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                password="Short1!",
                name="Test User",
            )
        assert "at least 8 characters" in str(exc_info.value)

    @pytest.mark.unit
    def test_password_without_uppercase(self):
        """Password without uppercase letter should fail."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                password="securep@ss123",
                name="Test User",
            )
        assert "uppercase" in str(exc_info.value)

    @pytest.mark.unit
    def test_password_without_number(self):
        """Password without number should fail."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                password="SecureP@ssword",
                name="Test User",
            )
        assert "number" in str(exc_info.value)

    @pytest.mark.unit
    def test_password_without_special_character(self):
        """Password without special character should fail."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                password="SecurePass123",
                name="Test User",
            )
        assert "special character" in str(exc_info.value)

    @pytest.mark.unit
    def test_invalid_email_format(self):
        """Invalid email format should fail."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="not-an-email",
                password="SecureP@ss123",
                name="Test User",
            )
        assert "email" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_empty_name_is_allowed(self):
        """Empty name is currently allowed by schema (no min_length constraint)."""
        # Note: This documents current behavior. Add min_length=1 to name field if validation is desired.
        user = UserCreate(
            email="test@example.com",
            password="SecureP@ss123",
            name="",
        )
        assert user.name == ""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "password,expected_valid",
        [
            ("SecureP@ss123", True),  # Valid
            ("P@ssw0rd", True),  # Exactly 8 chars
            ("MySuper$ecure123", True),  # Long password
            ("Test!1Aa", True),  # Minimum valid
            ("12345678", False),  # No uppercase, no special
            ("ABCDEFGH", False),  # No lowercase, no number, no special
            ("abcdefgh", False),  # No uppercase, no number, no special
            ("Abcdefg1", False),  # No special
            ("Abcdef!@", False),  # No number
        ],
    )
    def test_password_validation_matrix(self, password: str, expected_valid: bool):
        """Test various password combinations."""
        if expected_valid:
            user = UserCreate(
                email="test@example.com",
                password=password,
                name="Test User",
            )
            assert user.password == password
        else:
            with pytest.raises(ValidationError):
                UserCreate(
                    email="test@example.com",
                    password=password,
                    name="Test User",
                )


class TestUserLogin:
    """Tests for UserLogin schema."""

    @pytest.mark.unit
    def test_valid_login(self):
        """Valid login data should work."""
        login = UserLogin(
            email="test@example.com",
            password="anypassword",
        )
        assert login.email == "test@example.com"
        assert login.password == "anypassword"

    @pytest.mark.unit
    def test_login_invalid_email(self):
        """Invalid email format should fail."""
        with pytest.raises(ValidationError):
            UserLogin(
                email="not-valid",
                password="password",
            )


class TestUserResponse:
    """Tests for UserResponse schema."""

    @pytest.mark.unit
    def test_user_response_from_attributes(self):
        """UserResponse should serialize from ORM object."""

        class MockUser:
            id = uuid.uuid4()
            email = "test@example.com"
            name = "Test User"
            is_active = True
            created_at = datetime.now(timezone.utc)

        response = UserResponse.model_validate(MockUser())
        assert response.email == "test@example.com"
        assert response.name == "Test User"
        assert response.is_active is True


class TestTokenResponse:
    """Tests for TokenResponse schema."""

    @pytest.mark.unit
    def test_token_response(self):
        """TokenResponse should have correct structure."""
        response = TokenResponse(
            access_token="access123",
            refresh_token="refresh456",
            expires_in=3600,
        )
        assert response.access_token == "access123"
        assert response.refresh_token == "refresh456"
        assert response.token_type == "bearer"
        assert response.expires_in == 3600


class TestJobResponse:
    """Tests for JobResponse schema."""

    @pytest.mark.unit
    def test_job_response_from_job(self):
        """JobResponse.from_job should correctly convert Job object."""

        class MockJob:
            id = uuid.uuid4()
            status = JobStatus.QUEUED
            video_format = "mp4"
            video_size_bytes = 10_000_000
            original_filename = "test.mp4"
            frame_count = None
            zip_size_bytes = None
            processing_time_seconds = None
            error_code = None
            error_message = None
            retry_count = 0
            created_at = datetime.now(timezone.utc)
            started_at = None
            completed_at = None
            expires_at = None
            zip_path = None

        response = JobResponse.from_job(MockJob())
        assert response.status == JobStatus.QUEUED
        assert response.video_format == "mp4"
        assert response.download_available is False

    @pytest.mark.unit
    def test_job_response_download_available_when_done(self):
        """download_available should be True when status is DONE and zip_path exists."""

        class MockJob:
            id = uuid.uuid4()
            status = JobStatus.DONE
            video_format = "mp4"
            video_size_bytes = 10_000_000
            original_filename = "test.mp4"
            frame_count = 60
            zip_size_bytes = 5_000_000
            processing_time_seconds = 30
            error_code = None
            error_message = None
            retry_count = 0
            created_at = datetime.now(timezone.utc)
            started_at = datetime.now(timezone.utc)
            completed_at = datetime.now(timezone.utc)
            expires_at = None
            zip_path = "videos/user/job/output.zip"

        response = JobResponse.from_job(MockJob())
        assert response.status == JobStatus.DONE
        assert response.download_available is True
        assert response.frame_count == 60

    @pytest.mark.unit
    def test_job_response_download_not_available_when_done_without_zip(self):
        """download_available should be False when DONE but zip_path is None."""

        class MockJob:
            id = uuid.uuid4()
            status = JobStatus.DONE
            video_format = "mp4"
            video_size_bytes = 10_000_000
            original_filename = "test.mp4"
            frame_count = 60
            zip_size_bytes = None
            processing_time_seconds = 30
            error_code = None
            error_message = None
            retry_count = 0
            created_at = datetime.now(timezone.utc)
            started_at = None
            completed_at = None
            expires_at = None
            zip_path = None

        response = JobResponse.from_job(MockJob())
        assert response.download_available is False


class TestUploadResponse:
    """Tests for UploadResponse schema."""

    @pytest.mark.unit
    def test_upload_response(self):
        """UploadResponse should have correct structure."""
        job_id = uuid.uuid4()
        response = UploadResponse(
            job_id=job_id,
            status=JobStatus.QUEUED,
            message="Video queued for processing",
        )
        assert response.job_id == job_id
        assert response.status == JobStatus.QUEUED


class TestDownloadResponse:
    """Tests for DownloadResponse schema."""

    @pytest.mark.unit
    def test_download_response(self):
        """DownloadResponse should have correct structure."""
        response = DownloadResponse(
            download_url="https://example.com/download",
            expires_in=900,
            filename="video_frames.zip",
        )
        assert response.download_url == "https://example.com/download"
        assert response.expires_in == 900
        assert response.filename == "video_frames.zip"


class TestJobStatusResponse:
    """Tests for JobStatusResponse schema."""

    @pytest.mark.unit
    def test_job_status_response(self):
        """JobStatusResponse should have correct structure."""
        job_id = uuid.uuid4()
        response = JobStatusResponse(
            id=job_id,
            status=JobStatus.PROCESSING,
            progress="extracting_frames",
            message="Processing video",
        )
        assert response.id == job_id
        assert response.status == JobStatus.PROCESSING
        assert response.progress == "extracting_frames"
