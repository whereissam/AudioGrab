"""Amazon S3 and S3-compatible storage provider."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from .base import (
    CloudProvider,
    CloudUploadResult,
    ProviderConfig,
    ProviderType,
    UploadProgress,
)

logger = logging.getLogger(__name__)


class S3Provider(CloudProvider):
    """Amazon S3 and S3-compatible cloud storage provider."""

    def __init__(self, config: ProviderConfig):
        """
        Initialize S3 provider.

        Config credentials should contain:
            - access_key_id: AWS access key ID
            - secret_access_key: AWS secret access key

        Config settings can contain:
            - bucket: S3 bucket name
            - region: AWS region (default: us-east-1)
            - endpoint_url: Custom endpoint for S3-compatible services
        """
        super().__init__(config)
        self._client = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.S3

    def _get_client(self):
        """Get or create boto3 S3 client."""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config as BotoConfig
            except ImportError:
                raise ImportError(
                    "boto3 not installed. Install with: pip install boto3"
                )

            credentials = self.config.credentials
            settings = self.config.settings

            boto_config = BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            )

            self._client = boto3.client(
                "s3",
                aws_access_key_id=credentials.get("access_key_id"),
                aws_secret_access_key=credentials.get("secret_access_key"),
                region_name=settings.get("region", "us-east-1"),
                endpoint_url=settings.get("endpoint_url"),
                config=boto_config,
            )

        return self._client

    @property
    def bucket(self) -> str:
        """Get the configured S3 bucket name."""
        return self.config.settings.get("bucket", "")

    async def validate_credentials(self) -> bool:
        """Validate S3 credentials by listing buckets."""
        try:
            client = self._get_client()
            await asyncio.to_thread(client.list_buckets)
            return True
        except Exception as e:
            logger.error(f"S3 credential validation failed: {e}")
            return False

    async def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None,
    ) -> CloudUploadResult:
        """Upload file to S3 with multipart support for large files."""
        start_time = time.time()

        if not local_path.exists():
            return CloudUploadResult(
                success=False,
                provider_type=self.provider_type,
                error=f"Local file not found: {local_path}",
            )

        file_size = local_path.stat().st_size
        bytes_uploaded = 0

        def progress_handler(bytes_amount):
            nonlocal bytes_uploaded
            bytes_uploaded += bytes_amount
            if progress_callback:
                elapsed = time.time() - start_time
                speed = bytes_uploaded / elapsed if elapsed > 0 else 0
                progress_callback(
                    UploadProgress(
                        bytes_uploaded=bytes_uploaded,
                        total_bytes=file_size,
                        percentage=(bytes_uploaded / file_size) * 100,
                        speed_bytes_per_sec=speed,
                    )
                )

        try:
            client = self._get_client()

            # Use multipart upload for files > 100MB
            transfer_config = None
            if file_size > 100 * 1024 * 1024:
                try:
                    from boto3.s3.transfer import TransferConfig
                    transfer_config = TransferConfig(
                        multipart_threshold=100 * 1024 * 1024,
                        max_concurrency=10,
                        multipart_chunksize=100 * 1024 * 1024,
                    )
                except ImportError:
                    pass

            await asyncio.to_thread(
                client.upload_file,
                str(local_path),
                self.bucket,
                remote_path,
                Callback=progress_handler,
                Config=transfer_config,
            )

            # Generate URL
            endpoint_url = self.config.settings.get("endpoint_url")
            region = self.config.settings.get("region", "us-east-1")

            if endpoint_url:
                cloud_url = f"{endpoint_url}/{self.bucket}/{remote_path}"
            else:
                cloud_url = f"https://{self.bucket}.s3.{region}.amazonaws.com/{remote_path}"

            elapsed = time.time() - start_time
            logger.info(f"Uploaded to S3: {remote_path} ({file_size / (1024**2):.1f} MB in {elapsed:.1f}s)")

            return CloudUploadResult(
                success=True,
                provider_type=self.provider_type,
                cloud_url=cloud_url,
                cloud_path=f"s3://{self.bucket}/{remote_path}",
                bytes_uploaded=file_size,
                upload_time_seconds=elapsed,
            )

        except Exception as e:
            logger.exception(f"S3 upload error: {e}")
            return CloudUploadResult(
                success=False,
                provider_type=self.provider_type,
                error=str(e),
            )

    async def delete_file(self, remote_path: str) -> bool:
        """Delete a file from S3."""
        try:
            client = self._get_client()
            await asyncio.to_thread(
                client.delete_object,
                Bucket=self.bucket,
                Key=remote_path,
            )
            return True
        except Exception as e:
            logger.error(f"S3 delete error: {e}")
            return False

    async def list_files(
        self,
        remote_path: str = "",
        limit: int = 100,
    ) -> list[dict]:
        """List files in S3 bucket."""
        try:
            client = self._get_client()

            params = {
                "Bucket": self.bucket,
                "MaxKeys": limit,
            }
            if remote_path:
                params["Prefix"] = remote_path

            response = await asyncio.to_thread(client.list_objects_v2, **params)

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "etag": obj.get("ETag", "").strip('"'),
                })

            return files

        except Exception as e:
            logger.error(f"S3 list error: {e}")
            return []

    async def get_file_url(
        self,
        remote_path: str,
        expires_in_seconds: int = 3600,
    ) -> Optional[str]:
        """Generate a pre-signed URL for S3 file."""
        try:
            client = self._get_client()

            url = await asyncio.to_thread(
                client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self.bucket, "Key": remote_path},
                ExpiresIn=expires_in_seconds,
            )

            return url

        except Exception as e:
            logger.error(f"S3 presigned URL error: {e}")
            return None


def create_s3_provider_from_env() -> Optional[S3Provider]:
    """Create S3 provider from environment variables."""
    from ...config import get_settings
    settings = get_settings()

    if not settings.s3_access_key_id or not settings.s3_secret_access_key:
        return None

    config = ProviderConfig(
        id="env-s3",
        provider_type=ProviderType.S3,
        name="S3 (from environment)",
        credentials={
            "access_key_id": settings.s3_access_key_id,
            "secret_access_key": settings.s3_secret_access_key,
        },
        settings={
            "bucket": settings.s3_bucket or "",
            "region": settings.s3_region,
            "endpoint_url": settings.s3_endpoint_url,
        },
    )

    return S3Provider(config)
