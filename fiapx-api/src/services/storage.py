from pathlib import Path
from typing import BinaryIO

import boto3
import structlog
from botocore.client import Config
from botocore.exceptions import ClientError

from src.core.config import settings

logger = structlog.get_logger()


class StorageService:
    """S3-compatible storage service for MinIO/S3."""

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

        # Client for presigned URLs (external access)
        external_endpoint = settings.minio_external_endpoint or endpoint
        if not external_endpoint.startswith(("http://", "https://")):
            external_endpoint = f"http://{external_endpoint}"

        self.presign_client = boto3.client(
            "s3",
            endpoint_url=external_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
        )

    def upload_file(self, file_obj: BinaryIO, key: str, content_type: str | None = None) -> str:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        self.client.upload_fileobj(file_obj, self.bucket, key, ExtraArgs=extra_args)
        logger.info("file_uploaded", bucket=self.bucket, key=key)
        return key

    def generate_presigned_url(
        self, key: str, expires_in: int | None = None, filename: str | None = None
    ) -> str:
        if expires_in is None:
            expires_in = settings.presigned_url_expiry_seconds

        params = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        return self.presign_client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)

    def file_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def ensure_bucket_exists(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)
            logger.info("bucket_created", bucket=self.bucket)
