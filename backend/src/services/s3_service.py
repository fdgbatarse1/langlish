"""S3 service module for handling AWS S3 operations."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from src.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_S3_BUCKET_NAME,
    AWS_S3_REGION,
)

logger = logging.getLogger(__name__)


class S3Service:
    """Service class for AWS S3 operations."""

    def __init__(self) -> None:
        """Initialize S3 client with credentials from config."""
        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_S3_REGION,
            )
            self.bucket_name = AWS_S3_BUCKET_NAME
            logger.info(f"✅ S3 client initialized for bucket: {self.bucket_name}")
        except NoCredentialsError:
            logger.error("🔴 AWS credentials not found in configuration")
            raise
        except Exception as e:
            logger.error(f"🔴 Error initializing S3 client: {e}")
            raise

    def upload_audio(
        self,
        audio_data: bytes,
        file_name: str,
        content_type: str = "audio/webm",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Upload audio data to S3.

        Args:
            audio_data: Audio file data as bytes
            file_name: Name for the file in S3
            content_type: MIME type of the audio file
            metadata: Optional metadata to attach to the file

        Returns:
            str: S3 URL of the uploaded file, or None if upload fails
        """
        try:
            # Add timestamp to filename to ensure uniqueness
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"audio/{timestamp}_{file_name}"

            # Prepare metadata
            if metadata is None:
                metadata = {}
            metadata["upload_timestamp"] = datetime.utcnow().isoformat()

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=audio_data,
                ContentType=content_type,
                Metadata=metadata,
            )

            # Generate URL
            s3_url = f"https://{self.bucket_name}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"✅ Audio uploaded successfully to S3: {s3_url}")
            return s3_url

        except ClientError as e:
            logger.error(f"🔴 AWS S3 client error: {e}")
            return None
        except Exception as e:
            logger.error(f"🔴 Unexpected error uploading to S3: {e}")
            return None

    def generate_presigned_url(
        self, s3_key: str, expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for S3 object access.

        Args:
            s3_key: The S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            str: Presigned URL, or None if generation fails
        """
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
            logger.info(f"✅ Generated presigned URL for {s3_key}")
            return url
        except ClientError as e:
            logger.error(f"🔴 Error generating presigned URL: {e}")
            return None

    def upload_pcm_audio(
        self,
        pcm_data: bytes,
        session_id: str,
        audio_type: str = "user",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Upload PCM audio data to S3.

        Args:
            pcm_data: PCM audio data as bytes
            session_id: Unique session identifier
            audio_type: Type of audio ("user" or "assistant")
            metadata: Optional metadata to attach to the file

        Returns:
            str: S3 URL of the uploaded file, or None if upload fails
        """
        file_name = f"{session_id}_{audio_type}.pcm"
        return self.upload_audio(
            audio_data=pcm_data,
            file_name=file_name,
            content_type="audio/pcm",
            metadata=metadata,
        )
    
    def upload_text(
        self,
        text_data: str,
        file_name: str,
        content_type: str = "application/json",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Upload text (e.g., JSON) data to S3.

        Args:
            text_data: Text content to upload
            file_name: Desired filename in S3
            content_type: MIME type (default: application/json)
            metadata: Optional metadata dictionary

        Returns:
            str: S3 URL of the uploaded file, or None if upload fails
        """
        try:
            # Add timestamp to filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"conversations/{timestamp}_{file_name}"

            # Prepare metadata
            if metadata is None:
                metadata = {}
            metadata["upload_timestamp"] = datetime.utcnow().isoformat()

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=text_data.encode("utf-8"),
                ContentType=content_type,
                Metadata=metadata,
            )

            # Generate URL
            s3_url = f"https://{self.bucket_name}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"✅ Text uploaded successfully to S3: {s3_url}")
            return s3_url

        except ClientError as e:
            logger.error(f"🔴 AWS S3 client error: {e}")
            return None
        except Exception as e:
            logger.error(f"🔴 Unexpected error uploading text to S3: {e}")
            return None
    



# Create a singleton instance
s3_service = S3Service() if AWS_S3_BUCKET_NAME else None 