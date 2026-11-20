"""
AWS S3 client and storage framework for Crash Out assets and video outputs.

Supports:
- Direct S3 upload/download with boto3
- Local filesystem fallback when AWS credentials or buckets are not configured
- Generating pre-signed URLs for public video sharing
- Syncing episode outputs to S3
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from app.config import config
from app.paths import OUTPUT_DIR

logger = logging.getLogger("app.storage")


class S3StorageService:
    def __init__(self):
        self.bucket_name = (os.getenv("AWS_S3_BUCKET") or "").strip()
        self.region_name = (os.getenv("AWS_REGION") or "us-east-1").strip()
        self.access_key = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
        self.secret_key = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
        self.endpoint_url = (os.getenv("AWS_ENDPOINT_URL") or "").strip() or None
        self._s3_client = None

        if self.is_configured:
            try:
                import boto3

                client_kwargs: Dict[str, Any] = {"region_name": self.region_name}
                if self.access_key and self.secret_key:
                    client_kwargs["aws_access_key_id"] = self.access_key
                    client_kwargs["aws_secret_access_key"] = self.secret_key
                if self.endpoint_url:
                    client_kwargs["endpoint_url"] = self.endpoint_url

                self._s3_client = boto3.client("s3", **client_kwargs)
                logger.info("AWS S3 client initialized for bucket: %s (%s)", self.bucket_name, self.region_name)
            except Exception as exc:
                logger.warning("Failed to initialize boto3 S3 client: %s. Falling back to local storage.", exc)
                self._s3_client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.bucket_name)

    def upload_file(self, local_path: str, s3_key: str, content_type: Optional[str] = None) -> Optional[str]:
        """Uploads a local file to S3. Returns the S3 URI or None."""
        if not self._s3_client:
            logger.debug("S3 not configured. Local file preserved at: %s", local_path)
            return None

        if not os.path.isfile(local_path):
            logger.error("Local file does not exist: %s", local_path)
            return None

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        elif local_path.endswith(".mp4"):
            extra_args["ContentType"] = "video/mp4"
        elif local_path.endswith(".webm"):
            extra_args["ContentType"] = "video/webm"
        elif local_path.endswith(".wav"):
            extra_args["ContentType"] = "audio/wav"
        elif local_path.endswith(".mp3"):
            extra_args["ContentType"] = "audio/mpeg"
        elif local_path.endswith(".json"):
            extra_args["ContentType"] = "application/json"
        elif local_path.endswith(".png"):
            extra_args["ContentType"] = "image/png"

        try:
            self._s3_client.upload_file(
                Filename=local_path,
                Bucket=self.bucket_name,
                Key=s3_key,
                ExtraArgs=extra_args or None,
            )
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info("Uploaded %s -> %s", local_path, s3_uri)
            return s3_uri
        except Exception as exc:
            logger.error("Failed uploading %s to s3://%s/%s: %s", local_path, self.bucket_name, s3_key, exc)
            return None

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Downloads an object from S3 to a local destination."""
        if not self._s3_client:
            return False

        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        try:
            self._s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info("Downloaded s3://%s/%s -> %s", self.bucket_name, s3_key, local_path)
            return True
        except Exception as exc:
            logger.error("Failed downloading s3://%s/%s: %s", self.bucket_name, s3_key, exc)
            return False

    def generate_presigned_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a pre-signed URL to share an S3 object."""
        if not self._s3_client:
            return None

        try:
            url = self._s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expires_in,
            )
            return url
        except Exception as exc:
            logger.error("Failed generating presigned URL for %s: %s", s3_key, exc)
            return None

    def sync_episode_folder(self, episode_id: str, episode_folder: str) -> List[str]:
        """Upload all video and json outputs from an episode folder to S3."""
        if not self._s3_client or not os.path.isdir(episode_folder):
            return []

        uploaded_uris = []
        for root, _, files in os.walk(episode_folder):
            for file in files:
                local_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_path, episode_folder).replace("\\", "/")
                s3_key = f"episodes/{episode_id}/{rel_path}"
                uri = self.upload_file(local_path, s3_key)
                if uri:
                    uploaded_uris.append(uri)
        return uploaded_uris

    def get_media_url(self, episode_id: str, rel_path: str, fallback_local_url: str = "") -> str:
        """
        Returns an S3 presigned or direct URL if S3 is configured;
        otherwise returns fallback_local_url.
        """
        if not self._s3_client:
            return fallback_local_url
        clean_rel = rel_path.replace("\\", "/").lstrip("/")
        s3_key = f"episodes/{episode_id}/{clean_rel}"
        url = self.generate_presigned_url(s3_key, expires_in=86400)
        return url or fallback_local_url


s3_service = S3StorageService()
s3_storage = s3_service


def get_s3_service() -> S3StorageService:
    return s3_service
