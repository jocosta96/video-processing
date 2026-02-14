import shutil
import subprocess
import zipfile
from pathlib import Path

import structlog

logger = structlog.get_logger()


class FFmpegError(Exception):
    """Exception raised when FFmpeg processing fails."""
    pass


class VideoProcessor:
    """Video processor that extracts frames using FFmpeg."""

    def extract_frames(self, video_path: str, output_dir: str, fps: int = 1) -> list[str]:
        """
        Extract frames from video using FFmpeg.
        Command: ffmpeg -i {video_path} -vf fps=1 -y {output_dir}/frame_%04d.png
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", f"fps={fps}",
            "-y", str(output_path / "frame_%04d.png"),
        ]

        logger.info("ffmpeg_started", video_path=video_path, fps=fps)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, check=False)
        except subprocess.TimeoutExpired as e:
            raise FFmpegError(f"FFmpeg timeout: {e}") from e

        if result.returncode != 0:
            logger.error("ffmpeg_failed", returncode=result.returncode, stderr=result.stderr[:500])
            raise FFmpegError(f"FFmpeg failed: {result.stderr}")

        frames = sorted(output_path.glob("frame_*.png"))
        logger.info("ffmpeg_completed", frame_count=len(frames))
        return [f.name for f in frames]

    def create_zip(self, frames_dir: str, output_path: str) -> tuple[int, int]:
        """Create ZIP file with extracted frames. Returns (zip_size, frame_count)."""
        frames_path = Path(frames_dir)
        frames = sorted(frames_path.glob("frame_*.png"))

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for frame in frames:
                zf.write(frame, frame.name)

        zip_size = Path(output_path).stat().st_size
        logger.info("zip_created", path=output_path, frame_count=len(frames), size=zip_size)
        return zip_size, len(frames)

    def cleanup(self, directory: str) -> None:
        """Remove directory and contents."""
        path = Path(directory)
        if path.exists():
            shutil.rmtree(path)
