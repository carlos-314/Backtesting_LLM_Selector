import io

import boto3
from botocore.client import Config

from app.config import settings

_client = None


def get_s3_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        # Ensure bucket exists
        try:
            _client.head_bucket(Bucket=settings.MINIO_BUCKET)
        except Exception:
            _client.create_bucket(Bucket=settings.MINIO_BUCKET)
    return _client


def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    client = get_s3_client()
    client.upload_fileobj(io.BytesIO(data), settings.MINIO_BUCKET, key, ExtraArgs={"ContentType": content_type})
    return key


def download_file(key: str) -> bytes:
    client = get_s3_client()
    buf = io.BytesIO()
    client.download_fileobj(settings.MINIO_BUCKET, key, buf)
    buf.seek(0)
    return buf.read()


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.MINIO_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )
