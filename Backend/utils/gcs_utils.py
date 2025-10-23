from __future__ import annotations

import hashlib
import logging
from typing import Tuple

from fastapi import UploadFile
from google.cloud import storage

from config.settings import settings

logger = logging.getLogger(__name__)

class GCSManager:
    def __init__(self):
        self.client = storage.Client(project=settings.GCP_PROJECT_ID)
        self.bucket = self.client.bucket(settings.GCS_BUCKET_NAME)

    async def upload_file(self, file: UploadFile, destination_path: str) -> Tuple[str, str]:
        """Upload file to Google Cloud Storage"""
        try:
            blob = self.bucket.blob(destination_path)

            # Read file content
            content = await file.read()

            file_hash = hashlib.sha256(content).hexdigest()

            # Upload to GCS
            blob.upload_from_string(content, content_type=file.content_type)

            # Make blob publicly readable (optional)
            # blob.make_public()

            logger.info(f"File uploaded to GCS: {destination_path}")
            return f"gs://{settings.GCS_BUCKET_NAME}/{destination_path}", file_hash

        except Exception as e:
            logger.error(f"GCS upload error: {str(e)}")
            raise

    async def download_file(self, gcs_path: str, local_path: str):
        """Download file from GCS to local path"""
        try:
            # Extract blob name from gs:// path
            blob_name = gcs_path.replace(f"gs://{settings.GCS_BUCKET_NAME}/", "")
            blob = self.bucket.blob(blob_name)

            # Download to local file
            blob.download_to_filename(local_path)
            logger.info(f"File downloaded from GCS: {gcs_path}")

        except Exception as e:
            logger.error(f"GCS download error: {str(e)}")
            raise

    async def get_signed_url(self, gcs_path: str, expiration_minutes: int = 60) -> str:
        """Generate signed URL for private access"""
        try:
            blob_name = gcs_path.replace(f"gs://{settings.GCS_BUCKET_NAME}/", "")
            blob = self.bucket.blob(blob_name)

            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=expiration_minutes),
                method="GET"
            )
            return url

        except Exception as e:
            logger.error(f"Signed URL error: {str(e)}")
            raise
