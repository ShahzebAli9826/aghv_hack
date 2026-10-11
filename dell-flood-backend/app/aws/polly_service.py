import os
import base64
import hashlib
import logging
from typing import Dict, Any, Optional

from .s3_service import s3_service

logger = logging.getLogger("aegis.aws.polly")


def _has_real_aws_creds() -> bool:
    key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if not key or not secret:
        return False
    if key.startswith("your_") or secret.startswith("your_") or key == "AKIAIOSFODNN7EXAMPLE":
        return False
    return True


class PollyVoiceSynthesizer:
    """
    Amazon Polly Neural TTS Integration for Aegis:
    - Generates lifelike emergency voice warnings in Hindi ('Kajal'/'Aditi') & English ('Raveena')
    - Automatically caches/vaults MP3 audio to Amazon S3 for Twilio IVR and mobile app playback
    """

    def __init__(self):
        self.region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
        self.enabled = _has_real_aws_creds()
        self._polly = None
        if self.enabled:
            try:
                import boto3
                self._polly = boto3.client("polly", region_name=self.region)
            except Exception as e:
                logger.warning(f"Boto3 Polly initialization skipped: {e}")
                self.enabled = False

    def synthesize_emergency_alert(
        self,
        text: str,
        language: str = "hi-IN",
        voice_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes emergency speech into MP3 audio using Amazon Polly.
        Supports 'hi-IN' (Hindi) and 'en-IN' / 'en-US' (English).
        """
        is_hindi = language.lower().startswith("hi")
        selected_voice = voice_id or ("Aditi" if is_hindi else "Raveena")
        text_hash = hashlib.md5(f"{selected_voice}:{text}".encode("utf-8")).hexdigest()[:10]
        s3_key = f"audio/polly_alert_{selected_voice.lower()}_{text_hash}.mp3"

        if not self.enabled or not self._polly:
            return {
                "provider": "AWS_POLLY_SIMULATED",
                "voice_id": selected_voice,
                "language": "hi-IN" if is_hindi else "en-IN",
                "text": text,
                "s3_key": s3_key,
                "audio_url": s3_service._build_url(s3_key),
                "audio_base64": None,
                "status": "POLLY_SIMULATED_READY",
            }

        try:
            response = self._polly.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=selected_voice,
            )
            audio_stream = response.get("AudioStream")
            audio_bytes = audio_stream.read() if audio_stream else b""
            s3_res = s3_service.upload_bytes(audio_bytes, s3_key, content_type="audio/mpeg")
            return {
                "provider": "AMAZON_POLLY_LIVE",
                "voice_id": selected_voice,
                "language": "hi-IN" if is_hindi else "en-IN",
                "text": text,
                "s3_key": s3_key,
                "audio_url": s3_res.get("url"),
                "audio_base64": base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else None,
                "status": "SYNTHESIZED_LIVE",
            }
        except Exception as e:
            logger.warning(f"Polly speech synthesis fallback triggered: {e}")
            return {
                "provider": "AWS_POLLY_FALLBACK",
                "voice_id": selected_voice,
                "language": "hi-IN" if is_hindi else "en-IN",
                "text": text,
                "s3_key": s3_key,
                "audio_url": s3_service._build_url(s3_key),
                "audio_base64": None,
                "error": str(e),
                "status": "POLLY_SIMULATED_READY",
            }


polly_service = PollyVoiceSynthesizer()
