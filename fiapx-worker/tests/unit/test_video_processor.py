"""
Unit tests for src/services/video_processor.py

Tests FFmpeg frame extraction and ZIP creation.
"""

import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.video_processor import FFmpegError, VideoProcessor


class TestVideoProcessorExtractFrames:
    """Tests for VideoProcessor.extract_frames method."""

    @pytest.fixture
    def processor(self):
        """Create a VideoProcessor instance."""
        return VideoProcessor()

    @pytest.mark.unit
    def test_extract_frames_calls_ffmpeg_with_correct_command(self, processor, temp_dir):
        """FFmpeg should be called with correct arguments."""
        video_path = str(temp_dir / "input.mp4")
        output_dir = str(temp_dir / "frames")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            # Create mock frame files
            os.makedirs(output_dir, exist_ok=True)
            (Path(output_dir) / "frame_0001.png").touch()

            processor.extract_frames(video_path, output_dir)

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]

            assert "ffmpeg" in call_args
            assert "-i" in call_args
            assert video_path in call_args
            assert "-vf" in call_args
            assert "fps=1" in call_args
            assert "-y" in call_args

    @pytest.mark.unit
    def test_extract_frames_with_custom_fps(self, processor, temp_dir):
        """FFmpeg should use custom fps value."""
        video_path = str(temp_dir / "input.mp4")
        output_dir = str(temp_dir / "frames")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            os.makedirs(output_dir, exist_ok=True)

            processor.extract_frames(video_path, output_dir, fps=2)

            call_args = mock_run.call_args[0][0]
            assert "fps=2" in call_args

    @pytest.mark.unit
    def test_extract_frames_creates_output_directory(self, processor, temp_dir):
        """Output directory should be created if it doesn't exist."""
        video_path = str(temp_dir / "input.mp4")
        output_dir = str(temp_dir / "nested" / "frames")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            processor.extract_frames(video_path, output_dir)

            assert Path(output_dir).exists()

    @pytest.mark.unit
    def test_extract_frames_returns_frame_list(self, processor, temp_dir):
        """Method should return list of extracted frame filenames."""
        video_path = str(temp_dir / "input.mp4")
        output_dir = str(temp_dir / "frames")
        os.makedirs(output_dir, exist_ok=True)

        # Create mock frame files
        for i in range(5):
            (Path(output_dir) / f"frame_{i+1:04d}.png").touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            frames = processor.extract_frames(video_path, output_dir)

            assert len(frames) == 5
            assert "frame_0001.png" in frames
            assert "frame_0005.png" in frames

    @pytest.mark.unit
    def test_extract_frames_raises_on_ffmpeg_failure(self, processor, temp_dir):
        """FFmpegError should be raised when FFmpeg fails."""
        video_path = str(temp_dir / "input.mp4")
        output_dir = str(temp_dir / "frames")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Unknown codec: xyz"
            )

            with pytest.raises(FFmpegError) as exc_info:
                processor.extract_frames(video_path, output_dir)

            assert "FFmpeg failed" in str(exc_info.value)

    @pytest.mark.unit
    def test_extract_frames_raises_on_timeout(self, processor, temp_dir):
        """FFmpegError should be raised on timeout."""
        import subprocess

        video_path = str(temp_dir / "input.mp4")
        output_dir = str(temp_dir / "frames")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1800)

            with pytest.raises(FFmpegError) as exc_info:
                processor.extract_frames(video_path, output_dir)

            assert "timeout" in str(exc_info.value).lower()


class TestVideoProcessorCreateZip:
    """Tests for VideoProcessor.create_zip method."""

    @pytest.fixture
    def processor(self):
        """Create a VideoProcessor instance."""
        return VideoProcessor()

    @pytest.mark.unit
    def test_create_zip_creates_valid_zip_file(self, processor, sample_frames_dir, temp_dir):
        """ZIP file should be created with all frames."""
        zip_path = str(temp_dir / "output.zip")

        zip_size, frame_count = processor.create_zip(str(sample_frames_dir), zip_path)

        assert Path(zip_path).exists()
        assert zip_size > 0
        assert frame_count == 5

        # Verify ZIP contents
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert len(names) == 5
            assert "frame_0001.png" in names

    @pytest.mark.unit
    def test_create_zip_returns_correct_size(self, processor, sample_frames_dir, temp_dir):
        """Returned size should match actual file size."""
        zip_path = str(temp_dir / "output.zip")

        zip_size, _ = processor.create_zip(str(sample_frames_dir), zip_path)
        actual_size = Path(zip_path).stat().st_size

        assert zip_size == actual_size

    @pytest.mark.unit
    def test_create_zip_uses_deflate_compression(self, processor, sample_frames_dir, temp_dir):
        """ZIP should use DEFLATED compression."""
        zip_path = str(temp_dir / "output.zip")

        processor.create_zip(str(sample_frames_dir), zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                assert info.compress_type == zipfile.ZIP_DEFLATED

    @pytest.mark.unit
    def test_create_zip_with_empty_directory(self, processor, temp_dir):
        """Empty directory should create empty ZIP."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        zip_path = str(temp_dir / "output.zip")

        zip_size, frame_count = processor.create_zip(str(empty_dir), zip_path)

        assert frame_count == 0
        with zipfile.ZipFile(zip_path, "r") as zf:
            assert len(zf.namelist()) == 0


class TestVideoProcessorCleanup:
    """Tests for VideoProcessor.cleanup method."""

    @pytest.fixture
    def processor(self):
        """Create a VideoProcessor instance."""
        return VideoProcessor()

    @pytest.mark.unit
    def test_cleanup_removes_directory(self, processor, temp_dir):
        """Directory and contents should be removed."""
        test_dir = temp_dir / "to_delete"
        test_dir.mkdir()
        (test_dir / "file.txt").touch()
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "nested.txt").touch()

        processor.cleanup(str(test_dir))

        assert not test_dir.exists()

    @pytest.mark.unit
    def test_cleanup_handles_nonexistent_directory(self, processor, temp_dir):
        """Cleanup should not raise for non-existent directory."""
        nonexistent = str(temp_dir / "does_not_exist")

        # Should not raise
        processor.cleanup(nonexistent)


class TestFFmpegError:
    """Tests for FFmpegError exception."""

    @pytest.mark.unit
    def test_ffmpeg_error_is_exception(self):
        """FFmpegError should be an Exception."""
        error = FFmpegError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
