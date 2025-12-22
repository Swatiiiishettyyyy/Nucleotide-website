"""
S3 service for banner images.
Handles uploading, deleting, and URL generation for banner images stored in S3.
"""
import os
import boto3
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def get_env(key: str, default: str = None) -> str:
    """Get environment variable and strip surrounding quotes if present"""
    value = os.getenv(key, default)
    if value and isinstance(value, str):
        # Strip surrounding quotes (single or double)
        value = value.strip().strip('"').strip("'")
    return value


# AWS S3 Configuration from environment
AWS_ACCESS_KEY_ID = get_env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = get_env("AWS_SECRET_ACCESS_KEY")
AWS_REGION = get_env("AWS_REGION", "ap-south-1")
S3_BANNER_IMAGES_BUCKET = get_env("S3_BANNER_IMAGES_BUCKET")
S3_BANNER_IMAGES_PREFIX = get_env("S3_BANNER_IMAGES_PREFIX", "banner_images")
S3_BANNER_IMAGES_BASE_URL = get_env("S3_BANNER_IMAGES_BASE_URL")  # Optional CloudFront URL


class BannerImageS3Service:
    """Service for managing banner images in S3"""
    
    def __init__(self):
        """Initialize S3 client"""
        if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
            logger.warning("AWS credentials not configured. S3 operations will fail.")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        self.bucket = S3_BANNER_IMAGES_BUCKET
        self.prefix = S3_BANNER_IMAGES_PREFIX.rstrip('/')
        logger.info(f"BannerImageS3Service initialized for bucket: {self.bucket}")
    
    def upload_banner_image(
        self,
        banner_id: int,
        filename: str,
        file_content: bytes,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload banner image to S3.
        
        Args:
            banner_id: Banner ID
            filename: Original filename
            file_content: File content as bytes
            content_type: MIME type (e.g., 'image/jpeg', 'image/png')
        
        Returns:
            Full S3 URL of uploaded image
        """
        if not self.bucket:
            raise ValueError("S3_BANNER_IMAGES_BUCKET not configured")
        
        # Generate S3 key: prefix/banner_id_filename
        s3_key = f"{self.prefix}/{banner_id}_{filename}"
        
        try:
            logger.info(f"Uploading banner image to S3: {s3_key}")
            
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=file_content,
                **extra_args
            )
            
            logger.info(f"Successfully uploaded banner image to S3: {s3_key}")
            
            # Generate and return full URL
            return self.get_image_url(s3_key)
            
        except Exception as e:
            logger.error(f"Error uploading banner image to S3 {s3_key}: {e}", exc_info=True)
            raise
    
    def delete_banner_image(self, image_url: Optional[str]) -> bool:
        """
        Delete banner image from S3.
        
        Args:
            image_url: Full S3 URL or S3 key of the image to delete
        
        Returns:
            True if deleted successfully, False if image doesn't exist or URL is invalid
        """
        if not image_url:
            return False
        
        if not self.bucket:
            logger.warning("S3_BANNER_IMAGES_BUCKET not configured, cannot delete image")
            return False
        
        # Extract S3 key from URL
        s3_key = self.extract_s3_key(image_url)
        if not s3_key:
            logger.warning(f"Could not extract S3 key from URL: {image_url}")
            return False
        
        try:
            logger.info(f"Deleting banner image from S3: {s3_key}")
            
            self.s3_client.delete_object(
                Bucket=self.bucket,
                Key=s3_key
            )
            
            logger.info(f"Successfully deleted banner image from S3: {s3_key}")
            return True
            
        except Exception as e:
            # Check if it's a NoSuchKey error
            error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                logger.warning(f"Image not found in S3: {s3_key}")
                return False
            logger.error(f"Error deleting banner image from S3 {s3_key}: {e}", exc_info=True)
            # Don't raise - log error but return False
            return False
    
    def extract_s3_key(self, image_url: str) -> Optional[str]:
        """
        Extract S3 key from full URL.
        
        Handles:
        - S3 URLs: https://bucket.s3.region.amazonaws.com/key
        - CloudFront URLs: https://cloudfront-domain/key
        - Direct keys: key (if already just a key)
        
        Args:
            image_url: Full S3 URL or key
        
        Returns:
            S3 key or None if extraction fails
        """
        if not image_url:
            return None
        
        # If it's already just a key (no http/https), return as-is
        if not image_url.startswith('http://') and not image_url.startswith('https://'):
            return image_url
        
        try:
            # Parse URL
            parsed = urlparse(image_url)
            
            # Extract path and remove leading slash
            path = parsed.path.lstrip('/')
            
            # For S3 URLs: path is the key
            # For CloudFront URLs: path is also the key
            if path:
                return path
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting S3 key from URL {image_url}: {e}")
            return None
    
    def get_image_url(self, s3_key: str) -> str:
        """
        Generate full URL for S3 image.
        
        Args:
            s3_key: S3 key (path)
        
        Returns:
            Full URL (CloudFront if configured, otherwise S3 URL)
        """
        # If CloudFront base URL is configured, use it
        if S3_BANNER_IMAGES_BASE_URL:
            base_url = S3_BANNER_IMAGES_BASE_URL.rstrip('/')
            return f"{base_url}/{s3_key}"
        
        # Otherwise, construct S3 URL
        return f"https://{self.bucket}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"


# Create singleton instance
_banner_image_s3_service = None


def get_banner_image_s3_service() -> BannerImageS3Service:
    """Get singleton instance of BannerImageS3Service"""
    global _banner_image_s3_service
    if _banner_image_s3_service is None:
        _banner_image_s3_service = BannerImageS3Service()
    return _banner_image_s3_service

