"""
Integration test fixtures for fiapx-api.

These fixtures provide a full FastAPI test client with database and mocked external services.
"""

import os
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test environment
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DEBUG"] = "true"

from src.api.main import app
from src.models import get_db
from src.models.base import Base


@pytest.fixture(scope="function")
def integration_engine():
    """Create in-memory SQLite engine for integration tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def integration_session(integration_engine) -> Generator[Session, None, None]:
    """Create a database session for integration tests."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=integration_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(integration_engine, integration_session) -> Generator[TestClient, None, None]:
    """Create a test client with overridden dependencies."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=integration_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Mock external services
    mock_storage = MagicMock()
    mock_storage.upload_file.return_value = "test-key"
    mock_storage.file_exists.return_value = True
    mock_storage.generate_presigned_url.return_value = "https://example.com/signed"
    mock_storage.ensure_bucket_exists.return_value = None

    mock_publisher = MagicMock()
    mock_publisher.publish_video_job.return_value = None

    # Patch services where they're used (not where they're defined)
    with patch("src.api.main.StorageService", return_value=mock_storage), \
         patch("src.api.routers.videos.StorageService", return_value=mock_storage), \
         patch("src.api.routers.jobs.StorageService", return_value=mock_storage), \
         patch("src.api.routers.videos.get_publisher", return_value=mock_publisher):
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_client(integration_engine, integration_session) -> Generator[AsyncClient, None, None]:
    """Create an async test client for async endpoint testing."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=integration_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    mock_storage = MagicMock()
    mock_storage.upload_file.return_value = "test-key"
    mock_storage.file_exists.return_value = True
    mock_storage.generate_presigned_url.return_value = "https://example.com/signed"
    mock_storage.ensure_bucket_exists.return_value = None

    mock_publisher = MagicMock()
    mock_publisher.publish_video_job.return_value = None

    # Patch services where they're used (not where they're defined)
    with patch("src.api.main.StorageService", return_value=mock_storage), \
         patch("src.api.routers.videos.StorageService", return_value=mock_storage), \
         patch("src.api.routers.jobs.StorageService", return_value=mock_storage), \
         patch("src.api.routers.videos.get_publisher", return_value=mock_publisher):
        app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client: TestClient) -> dict:
    """Register a user and return credentials."""
    user_data = {
        "email": "test@example.com",
        "password": "SecureP@ss123",
        "name": "Test User",
    }
    response = client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201
    return user_data


@pytest.fixture
def auth_client(client: TestClient, registered_user: dict) -> tuple[TestClient, dict]:
    """Return client with auth headers."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers
