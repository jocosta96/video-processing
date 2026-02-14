"""
Shared fixtures for fiapx-worker tests.
"""

import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment before imports
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672"
os.environ["MINIO_ENDPOINT"] = "http://localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "minioadmin"
os.environ["MINIO_SECRET_KEY"] = "minioadmin"
os.environ["MINIO_BUCKET"] = "test-bucket"

from src.models.base import Base
from src.models.job import Job, JobStatus

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
# Job Fixtures
# ============================================================================


@pytest.fixture
def user_id() -> uuid.UUID:
    """Generate a random user ID."""
    return uuid.uuid4()


@pytest.fixture
def test_job(db_session: Session, user_id: uuid.UUID) -> Job:
    """Create and return a test job in QUEUED status."""
    job = Job(
        id=uuid.uuid4(),
        user_id=user_id,
        status=JobStatus.QUEUED,
        video_path=f"videos/{user_id}/test/input.mp4",
        video_size_bytes=10_000_000,
        video_format="mp4",
        original_filename="test_video.mp4",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ============================================================================
# File System Fixtures
# ============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_video_file(temp_dir: Path) -> Path:
    """Create a sample video file (fake bytes)."""
    video_path = temp_dir / "sample.mp4"
    # MP4 magic bytes + padding
    magic = b"\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d"
    video_path.write_bytes(magic + os.urandom(1024))
    return video_path


@pytest.fixture
def sample_frames_dir(temp_dir: Path) -> Path:
    """Create a directory with sample frame files."""
    frames_dir = temp_dir / "frames"
    frames_dir.mkdir()

    # Create sample PNG frames
    for i in range(5):
        frame_path = frames_dir / f"frame_{i+1:04d}.png"
        # PNG magic bytes + minimal data
        png_magic = b"\x89PNG\r\n\x1a\n"
        frame_path.write_bytes(png_magic + os.urandom(100))

    return frames_dir


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_redis():
    """Mock Redis client for deduplication and locking tests."""
    with patch("src.tasks.video.redis_client") as mock:
        mock.set.return_value = True
        mock.lock.return_value = MagicMock(
            acquire=MagicMock(return_value=True),
            release=MagicMock(),
        )
        yield mock


@pytest.fixture
def mock_storage():
    """Mock StorageService for tests that don't need real S3."""
    with patch("src.tasks.video.StorageService") as mock:
        instance = MagicMock()
        instance.download_file.return_value = "/tmp/video.mp4"
        instance.upload_file.return_value = "test-key"
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_ffmpeg():
    """Mock subprocess.run for FFmpeg tests."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stderr="")
        yield mock


@pytest.fixture
def mock_pika():
    """Mock pika for RabbitMQ tests."""
    with patch("src.tasks.video.pika") as mock:
        connection = MagicMock()
        channel = MagicMock()
        connection.channel.return_value = channel
        mock.BlockingConnection.return_value = connection
        mock.URLParameters.return_value = MagicMock()
        mock.BasicProperties.return_value = MagicMock()
        yield mock
