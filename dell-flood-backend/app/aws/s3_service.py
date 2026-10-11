import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("aegis.aws.s3")


def _has_real_aws_creds() -> bool:
    key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if not key or not secret:
        return False
    if key.startswith("your_") or secret.startswith("your_") or key == "AKIAIOSFODNN7EXAMPLE":
        return False
    return True


class S3DisasterStorage:
    """
    Amazon S3 Integration for Aegis:
    - Vaults AI-generated SITREP PDF reports (`reports/{filename}`)
    - Stores 4D ConvGRU nowcast raster PNG/GeoTIFF overlays (`nowcasts/{filename}`)
    - Generates 24h pre-signed URLs for SMS/SNS alerts and mobile app downloads
    """

    def __init__(self):
        self.region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
        self.bucket = os.getenv("AWS_S3_BUCKET", "aegis-disaster-vault")
        self.cloudfront_domain = os.getenv("AWS_CLOUDFRONT_DOMAIN", "").strip()
        self.enabled = _has_real_aws_creds()
        self._s3 = None
        if self.enabled:
            try:
                import boto3
                self._s3 = boto3.client("s3", region_name=self.region)
            except Exception as e:
                logger.warning(f"Boto3 S3 initialization skipped: {e}")
                self.enabled = False

    def _build_url(self, s3_key: str) -> str:
        if self.cloudfront_domain:
            domain = self.cloudfront_domain.rstrip("/")
            if not domain.startswith("http"):
                domain = f"https://{domain}"
            return f"{domain}/{s3_key.lstrip('/')}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{s3_key.lstrip('/')}"

    def upload_pdf_report(self, local_filepath: str, report_filename: Optional[str] = None) -> Dict[str, Any]:
        """Uploads a generated SITREP PDF report to Amazon S3 and returns a shareable URL."""
        filename = report_filename or os.path.basename(local_filepath)
        s3_key = f"reports/{filename}"
        local_fallback_url = f"/api/reports/download?filename={filename}"

        if not self.enabled or not self._s3 or not os.path.exists(local_filepath):
            return {
                "provider": "AWS_S3_SIMULATED",
                "bucket": self.bucket,
                "s3_key": s3_key,
                "url": local_fallback_url,
                "cloud_url_preview": self._build_url(s3_key),
                "status": "LOCAL_FALLBACK_ACTIVE",
            }

        try:
            self._s3.upload_file(
                local_filepath,
                self.bucket,
                s3_key,
                ExtraArgs={"ContentType": "application/pdf"},
            )
            presigned_url = self.generate_presigned_url(s3_key, expires_in=86400)
            return {
                "provider": "AMAZON_S3_LIVE",
                "bucket": self.bucket,
                "s3_key": s3_key,
                "url": presigned_url or self._build_url(s3_key),
                "cloud_url_preview": self._build_url(s3_key),
                "status": "UPLOADED_TO_S3",
            }
        except Exception as e:
            logger.warning(f"S3 PDF upload fallback triggered: {e}")
            return {
                "provider": "AWS_S3_FALLBACK",
                "bucket": self.bucket,
                "s3_key": s3_key,
                "url": local_fallback_url,
                "cloud_url_preview": self._build_url(s3_key),
                "error": str(e),
                "status": "LOCAL_FALLBACK_ACTIVE",
            }

    def upload_bytes(self, data: bytes, s3_key: str, content_type: str = "image/png") -> Dict[str, Any]:
        """Uploads raw bytes (such as 4D nowcast heatmap PNGs or Polly MP3 audio) to Amazon S3."""
        if not self.enabled or not self._s3:
            return {
                "provider": "AWS_S3_SIMULATED",
                "bucket": self.bucket,
                "s3_key": s3_key,
                "url": self._build_url(s3_key),
                "status": "SIMULATED",
            }

        try:
            self._s3.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=data,
                ContentType=content_type,
            )
            url = self.generate_presigned_url(s3_key, expires_in=86400) or self._build_url(s3_key)
            return {
                "provider": "AMAZON_S3_LIVE",
                "bucket": self.bucket,
                "s3_key": s3_key,
                "url": url,
                "status": "UPLOADED_TO_S3",
            }
        except Exception as e:
            logger.warning(f"S3 bytes upload fallback triggered: {e}")
            return {
                "provider": "AWS_S3_FALLBACK",
                "bucket": self.bucket,
                "s3_key": s3_key,
                "url": self._build_url(s3_key),
                "error": str(e),
                "status": "SIMULATED",
            }

    def generate_presigned_url(self, s3_key: str, expires_in: int = 86400) -> Optional[str]:
        """Generates a time-limited pre-signed S3 URL (default 24 hours)."""
        if not self.enabled or not self._s3:
            return self._build_url(s3_key)
        try:
            return self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expires_in,
            )
        except Exception as e:
            logger.warning(f"Presigned URL generation failed: {e}")
            return self._build_url(s3_key)


s3_service = S3DisasterStorage()
