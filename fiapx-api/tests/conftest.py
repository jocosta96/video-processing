"""
Shared fixtures for fiapx-api tests.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import MagicMock, patch

# ============================================================================
# Set test environment BEFORE any src imports
# ============================================================================
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672"
os.environ["MINIO_ENDPOINT"] = "http://localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "minioadmin"
os.environ["MINIO_SECRET_KEY"] = "minioadmin"
os.environ["MINIO_BUCKET"] = "test-bucket"

# Clear cached settings before any import
import src.core.config
src.core.config.get_settings.cache_clear()

import pytest
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.security import create_access_token, get_password_hash
from src.models.base import Base
from src.models.job import Job, JobStatus
from src.models.user import User

fake = Faker()


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def db_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a database session for testing."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ============================================================================
# User Fixtures
# ============================================================================


@pytest.fixture
def user_password() -> str:
    """Valid password that passes all validation rules."""
    return "SecureP@ss123"


@pytest.fixture
def user_data(user_password: str) -> dict:
    """Generate random user data."""
    return {
        "email": fake.email(),
        "password": user_password,
        "name": fake.name(),
    }


@pytest.fixture
def test_user(db_session: Session, user_password: str) -> User:
    """Create and return a test user."""
    user = User(
        id=uuid.uuid4(),
        email=fake.email(),
        password_hash=get_password_hash(user_password),
        name=fake.name(),
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session: Session, user_password: str) -> User:
    """Create and return an inactive test user."""
    user = User(
        id=uuid.uuid4(),
        email=fake.email(),
        password_hash=get_password_hash(user_password),
        name=fake.name(),
        is_active=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user: User) -> str:
    """Generate a valid JWT access token for the test user."""
    return create_access_token(data={"sub": str(test_user.id), "email": test_user.email})


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Generate authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {auth_token}"}


# ============================================================================
# Job Fixtures
# ============================================================================


@pytest.fixture
def test_job(db_session: Session, test_user: User) -> Job:
    """Create and return a test job."""
    job = Job(
        id=uuid.uuid4(),
        user_id=test_user.id,
        status=JobStatus.QUEUED,
        video_path=f"videos/{test_user.id}/test/input.mp4",
        video_size_bytes=10_000_000,
        video_format="mp4",
        original_filename="test_video.mp4",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def completed_job(db_session: Session, test_user: User) -> Job:
    """Create and return a completed job with ZIP."""
    job = Job(
        id=uuid.uuid4(),
        user_id=test_user.id,
        status=JobStatus.DONE,
        video_path=f"videos/{test_user.id}/test/input.mp4",
        video_size_bytes=10_000_000,
        video_format="mp4",
        original_filename="test_video.mp4",
        zip_path=f"videos/{test_user.id}/test/output.zip",
        frame_count=10,
        zip_size_bytes=5_000_000,
        processing_time_seconds=30,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def failed_job(db_session: Session, test_user: User) -> Job:
    """Create and return a failed job."""
    job = Job(
        id=uuid.uuid4(),
        user_id=test_user.id,
        status=JobStatus.FAILED,
        video_path=f"videos/{test_user.id}/test/input.mp4",
        video_size_bytes=10_000_000,
        video_format="mp4",
        original_filename="test_video.mp4",
        error_code="FFMPEG_ERROR",
        error_message="Unsupported codec",
        retry_count=3,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_storage():
    """Mock StorageService for tests that don't need real S3."""
    with patch("src.services.storage.StorageService") as mock:
        instance = MagicMock()
        instance.upload_file.return_value = "test-key"
        instance.file_exists.return_value = True
        instance.generate_presigned_url.return_value = "https://example.com/signed-url"
        instance.ensure_bucket_exists.return_value = None
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_publisher():
    """Mock MessagePublisher for tests that don't need RabbitMQ."""
    with patch("src.core.messaging.get_publisher") as mock:
        instance = MagicMock()
        instance.publish_video_job.return_value = None
        mock.return_value = instance
        yield instance


# ============================================================================
# Test Data Generators
# ============================================================================


def generate_video_bytes(size_kb: int = 100) -> bytes:
    """Generate fake video bytes for upload testing."""
    # MP4 magic bytes + random data
    magic = b"\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d"
    return magic + os.urandom(size_kb * 1024 - len(magic))


@pytest.fixture
def sample_video_bytes() -> bytes:
    """Generate sample video bytes."""
    return generate_video_bytes(100)
