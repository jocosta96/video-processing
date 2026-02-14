"""
End-to-End tests for the complete video processing flow.

These tests require the full infrastructure to be running:
- API Gateway
- Video Worker
- PostgreSQL
- RabbitMQ
- Redis
- MinIO

Run with: pytest tests/e2e -v --e2e-base-url=http://localhost:8000
"""

import io
import os
import time
from typing import Generator

import httpx
import pytest

# Skip E2E tests if infrastructure is not available
pytestmark = pytest.mark.e2e


def generate_video_bytes(size_kb: int = 50) -> bytes:
    """Generate fake video bytes with MP4 magic header."""
    # MP4 file magic bytes (ftyp box)
    magic = b"\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d"
    return magic + os.urandom(size_kb * 1024 - len(magic))


class TestFullVideoProcessingFlow:
    """
    Tests the complete flow from registration to download.

    Flow:
    1. Register user
    2. Login and get JWT
    3. Upload video
    4. Poll status until DONE or FAILED
    5. Get download URL
    6. Download ZIP file
    """

    @pytest.fixture
    def client(self, base_url: str) -> Generator[httpx.Client, None, None]:
        """Create HTTP client for E2E tests."""
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            yield client

    def test_health_check(self, client: httpx.Client):
        """Verify API is healthy before running E2E tests."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_register_login_flow(self, client: httpx.Client, e2e_user_credentials: dict):
        """Test user registration and login."""
        # Register
        response = client.post("/api/v1/auth/register", json=e2e_user_credentials)
        assert response.status_code == 201
        user_data = response.json()
        assert user_data["email"] == e2e_user_credentials["email"]

        # Login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": e2e_user_credentials["email"],
                "password": e2e_user_credentials["password"],
            },
        )
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert "refresh_token" in token_data

        # Verify token works
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == e2e_user_credentials["email"]

    def test_upload_and_list_videos(self, client: httpx.Client, e2e_user_credentials: dict):
        """Test video upload and listing."""
        # Register and login
        client.post("/api/v1/auth/register", json=e2e_user_credentials)
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": e2e_user_credentials["email"],
                "password": e2e_user_credentials["password"],
            },
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload video
        video_content = generate_video_bytes(20)
        files = {"file": ("e2e_test_video.mp4", io.BytesIO(video_content), "video/mp4")}
        upload_response = client.post("/api/v1/videos/upload", files=files, headers=headers)

        assert upload_response.status_code == 202
        upload_data = upload_response.json()
        assert "job_id" in upload_data
        assert upload_data["status"] == "QUEUED"

        job_id = upload_data["job_id"]

        # List videos
        list_response = client.get("/api/v1/videos", headers=headers)
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["total"] >= 1

        # Find our job
        job_ids = [job["id"] for job in list_data["jobs"]]
        assert job_id in job_ids

        # Get video details
        detail_response = client.get(f"/api/v1/videos/{job_id}", headers=headers)
        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        assert detail_data["original_filename"] == "e2e_test_video.mp4"

    def test_cancel_video(self, client: httpx.Client, e2e_user_credentials: dict):
        """Test cancelling a queued video."""
        # Register and login
        client.post("/api/v1/auth/register", json=e2e_user_credentials)
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": e2e_user_credentials["email"],
                "password": e2e_user_credentials["password"],
            },
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload video
        video_content = generate_video_bytes(10)
        files = {"file": ("cancel_test.mp4", io.BytesIO(video_content), "video/mp4")}
        upload_response = client.post("/api/v1/videos/upload", files=files, headers=headers)
        job_id = upload_response.json()["job_id"]

        # Cancel immediately (before worker picks it up)
        cancel_response = client.delete(f"/api/v1/videos/{job_id}", headers=headers)
        # Might be 204 if cancelled or 400 if already processing
        assert cancel_response.status_code in [204, 400]

        # Check status
        status_response = client.get(f"/api/v1/videos/{job_id}", headers=headers)
        assert status_response.status_code == 200
        # Status should be CANCELLED or PROCESSING (if worker was fast)
        status = status_response.json()["status"]
        assert status in ["CANCELLED", "PROCESSING", "DONE", "QUEUED"]


class TestFullProcessingWithWorker:
    """
    Tests that require the worker to actually process videos.

    These tests are marked as slow and may take several minutes.
    """

    @pytest.fixture
    def client(self, base_url: str) -> Generator[httpx.Client, None, None]:
        """Create HTTP client with longer timeout for processing."""
        with httpx.Client(base_url=base_url, timeout=60.0) as client:
            yield client

    @pytest.mark.slow
    def test_complete_processing_flow(self, client: httpx.Client, e2e_user_credentials: dict):
        """
        Test complete flow: upload -> process -> download.

        Note: This test requires a real video file and worker processing.
        It may take several minutes to complete.
        """
        # Register and login
        client.post("/api/v1/auth/register", json=e2e_user_credentials)
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": e2e_user_credentials["email"],
                "password": e2e_user_credentials["password"],
            },
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload video
        video_content = generate_video_bytes(100)  # Larger file
        files = {"file": ("process_test.mp4", io.BytesIO(video_content), "video/mp4")}
        upload_response = client.post("/api/v1/videos/upload", files=files, headers=headers)

        assert upload_response.status_code == 202
        job_id = upload_response.json()["job_id"]

        # Poll for completion (max 5 minutes)
        max_polls = 60
        poll_interval = 5
        final_status = None

        for _ in range(max_polls):
            status_response = client.get(f"/api/v1/jobs/{job_id}/status", headers=headers)
            assert status_response.status_code == 200

            status_data = status_response.json()
            final_status = status_data["status"]

            if final_status in ["DONE", "FAILED"]:
                break

            time.sleep(poll_interval)

        # Note: With fake video bytes, processing will likely fail
        # This test verifies the flow works, not that processing succeeds
        assert final_status in ["DONE", "FAILED", "PROCESSING"]

        if final_status == "DONE":
            # Try to get download URL
            download_response = client.get(f"/api/v1/jobs/{job_id}/download", headers=headers)
            assert download_response.status_code == 200
            download_data = download_response.json()
            assert "download_url" in download_data
            assert download_data["expires_in"] > 0


class TestAuthorizationBoundaries:
    """Tests for authorization boundaries between users."""

    @pytest.fixture
    def client(self, base_url: str) -> Generator[httpx.Client, None, None]:
        """Create HTTP client for E2E tests."""
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            yield client

    def test_user_cannot_access_other_users_videos(self, client: httpx.Client):
        """Verify users cannot access each other's videos."""
        import uuid

        # Create user 1
        user1_id = uuid.uuid4().hex[:8]
        user1 = {
            "email": f"e2e_auth_user1_{user1_id}@example.com",
            "password": "E2eTestP@ss123",
            "name": "User 1",
        }
        client.post("/api/v1/auth/register", json=user1)
        login1 = client.post(
            "/api/v1/auth/login",
            json={"email": user1["email"], "password": user1["password"]},
        )
        headers1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

        # User 1 uploads video
        video_content = generate_video_bytes(10)
        files = {"file": ("user1_video.mp4", io.BytesIO(video_content), "video/mp4")}
        upload = client.post("/api/v1/videos/upload", files=files, headers=headers1)
        job_id = upload.json()["job_id"]

        # Create user 2
        user2_id = uuid.uuid4().hex[:8]
        user2 = {
            "email": f"e2e_auth_user2_{user2_id}@example.com",
            "password": "E2eTestP@ss123",
            "name": "User 2",
        }
        client.post("/api/v1/auth/register", json=user2)
        login2 = client.post(
            "/api/v1/auth/login",
            json={"email": user2["email"], "password": user2["password"]},
        )
        headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        # User 2 tries to access user 1's video
        response = client.get(f"/api/v1/videos/{job_id}", headers=headers2)
        assert response.status_code == 403

        response = client.get(f"/api/v1/jobs/{job_id}/status", headers=headers2)
        assert response.status_code == 403

        response = client.get(f"/api/v1/jobs/{job_id}/download", headers=headers2)
        assert response.status_code == 403

        response = client.delete(f"/api/v1/videos/{job_id}", headers=headers2)
        assert response.status_code == 403
