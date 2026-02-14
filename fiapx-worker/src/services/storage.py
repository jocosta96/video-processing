from pathlib import Path

import boto3
import structlog
from botocore.client import Config

from src.core.config import settings

logger = structlog.get_logger()


class StorageService:
    """S3-compatible storage service."""

    def __init__(self) -> None:
        endpoint = settings.minio_endpoint
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = settings.minio_bucket

    def download_file(self, key: str, destination: str) -> str:
        """Download file from S3 to local path."""
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, destination)
        logger.info("file_downloaded", key=key, destination=destination)
        return destination

    def upload_file(self, local_path: str, key: str) -> str:
        """Upload file from local path to S3."""
        self.client.upload_file(local_path, self.bucket, key)
        logger.info("file_uploaded", key=key, local_path=local_path)
        return key
