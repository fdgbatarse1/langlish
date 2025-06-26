"""S3 service module for handling AWS S3 operations."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import json

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
        
    def upload_evaluation(
        self,
        evaluation_data: str,
        file_name: str = "evaluation_results.csv",
        content_type: str = "text/csv",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Upload evaluation data to S3.

        Args:
            evaluation_data: CSV content or evaluation text to upload
            file_name: Desired filename in S3 (default: evaluation_results.csv)
            content_type: MIME type (default: text/csv)
            metadata: Optional metadata dictionary

        Returns:
            str: S3 URL of the uploaded file, or None if upload fails
        """
        try:
            # Add timestamp to filename for evaluations
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"evaluations/{timestamp}_{file_name}"

            # Prepare evaluation-specific metadata
            if metadata is None:
                metadata = {}
            metadata.update({
                "upload_timestamp": datetime.utcnow().isoformat(),
                "data_type": "evaluation",
                "file_type": "csv" if content_type == "text/csv" else "text"
            })

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=evaluation_data.encode("utf-8"),
                ContentType=content_type,
                Metadata=metadata,
            )

            # Generate URL
            s3_url = f"https://{self.bucket_name}.s3.{AWS_S3_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"✅ Evaluation data uploaded successfully to S3: {s3_url}")
            return s3_url

        except ClientError as e:
            logger.error(f"🔴 AWS S3 client error during evaluation upload: {e}")
            return None
        except Exception as e:
            logger.error(f"🔴 Unexpected error uploading evaluation to S3: {e}")
            return None
        
    def pull_conversations_from_s3(self, type):
        """
        Pull all conversation files from S3 bucket using your S3Service.
        """
        
        if not self.s3_client: 
            logging.error("S3 service not initialized")
            return []
        
        bucket_name = self.bucket_name 
        if type == "streamline":
            prefix = 'conversations_streamline/'
        elif type == "agent_streamline":
            prefix = 'conversations_agent_streamline/'
        else:
            logging.error(f"Unknown type: {type}")
            return []
        
        try:
            # List all objects with the prefix using boto3 directly
            response = self.s3_client.list_objects_v2(  
                Bucket=bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                logging.warning(f"No objects found in s3://{bucket_name}/{prefix}")
                return []
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

            all_conversations = []

            for page in pages:
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    obj_key = obj['Key']
                    if obj_key.endswith('/') or not (obj_key.endswith('.json') or obj_key.endswith('.jsonl')):
                        continue
                    try:
                        response_obj = self.s3_client.get_object(Bucket=bucket_name, Key=obj_key)
                        obj_content = response_obj['Body'].read().decode('utf-8')

                        if obj_key.endswith('.json'):
                            data = json.loads(obj_content)
                            all_conversations.extend(data if isinstance(data, list) else [data])
                        elif obj_key.endswith('.jsonl'):
                            for line in obj_content.strip().split('\n'):
                                if line.strip():
                                    all_conversations.append(json.loads(line))

                        logging.info(f"✅ Processed {obj_key}: total so far = {len(all_conversations)}")

                    except Exception as e:
                        logging.error(f"❌ Error processing {obj_key}: {str(e)}")
                        continue

            logging.info(f"🎉 Total conversations pulled: {len(all_conversations)}")
            return all_conversations

            
        except Exception as e:
            logging.error(f"Error listing S3 objects: {str(e)}")
            return []
            



# Create a singleton instance
s3_service = S3Service() if AWS_S3_BUCKET_NAME else None 