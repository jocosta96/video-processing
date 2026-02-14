"""
Integration tests for job endpoints.

Tests /jobs/{id}/status, /jobs/{id}/download
"""

import io
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def generate_video_bytes(size_kb: int = 10) -> bytes:
    """Generate fake video bytes with MP4 magic header."""
    magic = b"\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d"
    return magic + os.urandom(size_kb * 1024 - len(magic))


class TestJobStatus:
    """Tests for GET /jobs/{job_id}/status endpoint."""

    @pytest.mark.integration
    def test_get_status_queued(self, auth_client: tuple[TestClient, dict]):
        """Should return QUEUED status for new upload."""
        client, headers = auth_client

        # Upload a video
        video_content = generate_video_bytes(10)
        files = {"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}
        upload_response = client.post("/api/v1/videos/upload", files=files, headers=headers)
        job_id = upload_response.json()["job_id"]

        # Get status
        response = client.get(f"/api/v1/jobs/{job_id}/status", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["status"] == "QUEUED"
        assert data["message"] is not None

    @pytest.mark.integration
    def test_get_status_not_found(self, auth_client: tuple[TestClient, dict]):
        """Non-existent job should return 404."""
        client, headers = auth_client

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/jobs/{fake_id}/status", headers=headers)

        assert response.status_code == 404

    @pytest.mark.integration
    def test_get_status_other_user(self, client: TestClient):
        """Should not access another user's job status."""
        # Register user 1 and upload video
        user1 = {"email": "status_user1@example.com", "password": "SecureP@ss123", "name": "User 1"}
        client.post("/api/v1/auth/register", json=user1)
        login1 = client.post("/api/v1/auth/login", json={"email": user1["email"], "password": user1["password"]})
        headers1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

        video_content = generate_video_bytes(10)
        files = {"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}
        upload = client.post("/api/v1/videos/upload", files=files, headers=headers1)
        job_id = upload.json()["job_id"]

        # Register user 2
        user2 = {"email": "status_user2@example.com", "password": "SecureP@ss123", "name": "User 2"}
        client.post("/api/v1/auth/register", json=user2)
        login2 = client.post("/api/v1/auth/login", json={"email": user2["email"], "password": user2["password"]})
        headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        # Try to access as user 2
        response = client.get(f"/api/v1/jobs/{job_id}/status", headers=headers2)

        assert response.status_code == 403


class TestJobDownload:
    """Tests for GET /jobs/{job_id}/download endpoint."""

    @pytest.mark.integration
    def test_download_not_complete(self, auth_client: tuple[TestClient, dict]):
        """Should return 400 for jobs not in DONE status."""
        client, headers = auth_client

        # Upload a video (will be in QUEUED status)
        video_content = generate_video_bytes(10)
        files = {"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}
        upload_response = client.post("/api/v1/videos/upload", files=files, headers=headers)
        job_id = upload_response.json()["job_id"]

        # Try to download
        response = client.get(f"/api/v1/jobs/{job_id}/download", headers=headers)

        assert response.status_code == 400
        assert "not complete" in response.json()["detail"].lower()

    @pytest.mark.integration
    def test_download_not_found(self, auth_client: tuple[TestClient, dict]):
        """Non-existent job should return 404."""
        client, headers = auth_client

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/jobs/{fake_id}/download", headers=headers)

        assert response.status_code == 404

    @pytest.mark.integration
    def test_download_without_auth(self, client: TestClient):
        """Download without auth should return 401 Unauthorized."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/jobs/{fake_id}/download")

        assert response.status_code == 401

    @pytest.mark.integration
    def test_download_other_user(self, client: TestClient):
        """Should not download another user's job."""
        # Register user 1 and upload video
        user1 = {"email": "dl_user1@example.com", "password": "SecureP@ss123", "name": "User 1"}
        client.post("/api/v1/auth/register", json=user1)
        login1 = client.post("/api/v1/auth/login", json={"email": user1["email"], "password": user1["password"]})
        headers1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

        video_content = generate_video_bytes(10)
        files = {"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}
        upload = client.post("/api/v1/videos/upload", files=files, headers=headers1)
        job_id = upload.json()["job_id"]

        # Register user 2
        user2 = {"email": "dl_user2@example.com", "password": "SecureP@ss123", "name": "User 2"}
        client.post("/api/v1/auth/register", json=user2)
        login2 = client.post("/api/v1/auth/login", json={"email": user2["email"], "password": user2["password"]})
        headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        # Try to download as user 2
        response = client.get(f"/api/v1/jobs/{job_id}/download", headers=headers2)

        assert response.status_code == 403


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.integration
    def test_health_check(self, client: TestClient):
        """Health endpoint should return 200."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.integration
    def test_root_endpoint(self, client: TestClient):
        """Root endpoint should return service info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
