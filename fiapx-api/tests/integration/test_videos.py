"""
Integration tests for video endpoints.

Tests /videos/upload, /videos, /videos/{id}, DELETE /videos/{id}
"""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient


def generate_video_bytes(size_kb: int = 10) -> bytes:
    """Generate fake video bytes with MP4 magic header."""
    magic = b"\x00\x00\x00\x1c\x66\x74\x79\x70\x69\x73\x6f\x6d"
    return magic + os.urandom(size_kb * 1024 - len(magic))


class TestVideoUpload:
    """Tests for POST /videos/upload endpoint."""

    @pytest.mark.integration
    def test_upload_success(self, auth_client: tuple[TestClient, dict]):
        """Valid video upload should return 202 with job info."""
        client, headers = auth_client

        video_content = generate_video_bytes(10)
        files = {"file": ("test_video.mp4", io.BytesIO(video_content), "video/mp4")}

        response = client.post("/api/v1/videos/upload", files=files, headers=headers)

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "QUEUED"
        assert "message" in data

    @pytest.mark.integration
    def test_upload_without_auth(self, client: TestClient):
        """Upload without authentication should return 401 Unauthorized."""
        video_content = generate_video_bytes(10)
        files = {"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}

        response = client.post("/api/v1/videos/upload", files=files)

        assert response.status_code == 401

    @pytest.mark.integration
    def test_upload_unsupported_format(self, auth_client: tuple[TestClient, dict]):
        """Unsupported file format should return 400."""
        client, headers = auth_client

        files = {"file": ("document.pdf", io.BytesIO(b"fake pdf"), "application/pdf")}

        response = client.post("/api/v1/videos/upload", files=files, headers=headers)

        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()

    @pytest.mark.integration
    def test_upload_no_filename(self, auth_client: tuple[TestClient, dict]):
        """Upload without filename should return 400 or 422."""
        client, headers = auth_client

        # Empty filename
        files = {"file": ("", io.BytesIO(b"content"), "video/mp4")}

        response = client.post("/api/v1/videos/upload", files=files, headers=headers)

        # FastAPI returns 422 for validation errors, but some APIs return 400
        assert response.status_code in (400, 422)

    @pytest.mark.integration
    @pytest.mark.parametrize(
        "extension,content_type",
        [
            (".mp4", "video/mp4"),
            (".avi", "video/x-msvideo"),
            (".mov", "video/quicktime"),
            (".mkv", "video/x-matroska"),
            (".webm", "video/webm"),
        ],
    )
    def test_upload_supported_formats(
        self,
        auth_client: tuple[TestClient, dict],
        extension: str,
        content_type: str,
    ):
        """All supported video formats should be accepted."""
        client, headers = auth_client

        video_content = generate_video_bytes(10)
        filename = f"video{extension}"
        files = {"file": (filename, io.BytesIO(video_content), content_type)}

        response = client.post("/api/v1/videos/upload", files=files, headers=headers)

        assert response.status_code == 202


class TestListVideos:
    """Tests for GET /videos endpoint."""

    @pytest.mark.integration
    def test_list_videos_empty(self, auth_client: tuple[TestClient, dict]):
        """New user should have empty video list."""
        client, headers = auth_client

        response = client.get("/api/v1/videos", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    @pytest.mark.integration
    def test_list_videos_with_uploads(self, auth_client: tuple[TestClient, dict]):
        """User should see their uploaded videos."""
        client, headers = auth_client

        # Upload a video
        video_content = generate_video_bytes(10)
        files = {"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}
        client.post("/api/v1/videos/upload", files=files, headers=headers)

        # List videos
        response = client.get("/api/v1/videos", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["original_filename"] == "test.mp4"

    @pytest.mark.integration
    def test_list_videos_pagination(self, auth_client: tuple[TestClient, dict]):
        """Pagination parameters should work correctly."""
        client, headers = auth_client

        # Upload multiple videos
        for i in range(3):
            video_content = generate_video_bytes(10)
            files = {"file": (f"video{i}.mp4", io.BytesIO(video_content), "video/mp4")}
            client.post("/api/v1/videos/upload", files=files, headers=headers)

        # Test limit
        response = client.get("/api/v1/videos?limit=2", headers=headers)
        data = response.json()
        assert len(data["jobs"]) == 2
        assert data["total"] == 3

        # Test skip
        response = client.get("/api/v1/videos?skip=2", headers=headers)
        data = response.json()
        assert len(data["jobs"]) == 1

    @pytest.mark.integration
    def test_list_videos_without_auth(self, client: TestClient):
        """Listing without auth should return 401 Unauthorized."""
        response = client.get("/api/v1/videos")

        assert response.status_code == 401


class TestGetVideo:
    """Tests for GET /videos/{job_id} endpoint."""

    @pytest.mark.integration
    def test_get_video_success(self, auth_client: tuple[TestClient, dict]):
        """Should return video details for owned job."""
        client, headers = auth_client

        # Upload a video
        video_content = generate_video_bytes(10)
        files = {"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}
        upload_response = client.post("/api/v1/videos/upload", files=files, headers=headers)
        job_id = upload_response.json()["job_id"]

        # Get video details
        response = client.get(f"/api/v1/videos/{job_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["status"] == "QUEUED"
        assert data["original_filename"] == "test.mp4"
        assert data["video_format"] == "mp4"

    @pytest.mark.integration
    def test_get_video_not_found(self, auth_client: tuple[TestClient, dict]):
        """Non-existent job should return 404."""
        client, headers = auth_client

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/videos/{fake_id}", headers=headers)

        assert response.status_code == 404

    @pytest.mark.integration
    def test_get_video_other_user(self, client: TestClient):
        """Should not access another user's video."""
        # Register and login user 1
        user1 = {
            "email": "user1@example.com",
            "password": "SecureP@ss123",
            "name": "User 1",
        }
        client.post("/api/v1/auth/register", json=user1)
        login1 = client.post(
            "/api/v1/auth/login",
            json={"email": user1["email"], "password": user1["password"]},
        )
        headers1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

        # Upload video as user 1
        video_content = generate_video_bytes(10)
        files = {"file": ("user1_video.mp4", io.BytesIO(video_content), "video/mp4")}
        upload = client.post("/api/v1/videos/upload", files=files, headers=headers1)
        job_id = upload.json()["job_id"]

        # Register and login user 2
        user2 = {
            "email": "user2@example.com",
            "password": "SecureP@ss123",
            "name": "User 2",
        }
        client.post("/api/v1/auth/register", json=user2)
        login2 = client.post(
            "/api/v1/auth/login",
            json={"email": user2["email"], "password": user2["password"]},
        )
        headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        # Try to access user 1's video as user 2
        response = client.get(f"/api/v1/videos/{job_id}", headers=headers2)

        assert response.status_code == 403


class TestCancelVideo:
    """Tests for DELETE /videos/{job_id} endpoint."""

    @pytest.mark.integration
    def test_cancel_queued_video(self, auth_client: tuple[TestClient, dict]):
        """Should cancel queued video successfully."""
        client, headers = auth_client

        # Upload a video
        video_content = generate_video_bytes(10)
        files = {"file": ("test.mp4", io.BytesIO(video_content), "video/mp4")}
        upload_response = client.post("/api/v1/videos/upload", files=files, headers=headers)
        job_id = upload_response.json()["job_id"]

        # Cancel the video
        response = client.delete(f"/api/v1/videos/{job_id}", headers=headers)

        assert response.status_code == 204

        # Verify status changed
        get_response = client.get(f"/api/v1/videos/{job_id}", headers=headers)
        assert get_response.json()["status"] == "CANCELLED"

    @pytest.mark.integration
    def test_cancel_not_found(self, auth_client: tuple[TestClient, dict]):
        """Cancelling non-existent job should return 404."""
        client, headers = auth_client

        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/videos/{fake_id}", headers=headers)

        assert response.status_code == 404

    @pytest.mark.integration
    def test_cancel_without_auth(self, client: TestClient):
        """Cancelling without auth should return 401 Unauthorized."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/videos/{fake_id}")

        assert response.status_code == 401
