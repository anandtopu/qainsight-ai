"""MinIO / S3-compatible object storage client."""
import aioboto3
from botocore.client import Config
from typing import AsyncGenerator

from app.core.config import settings


def get_s3_session() -> aioboto3.Session:
    return aioboto3.Session()


def get_s3_client_context():
    """Async context manager for S3 client."""
    session = get_s3_session()
    return session.client(
        "s3",
        endpoint_url=f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


async def list_objects(prefix: str, bucket: str = None) -> list[dict]:
    """List objects in the bucket with a given prefix."""
    bucket = bucket or settings.MINIO_BUCKET_NAME
    objects = []
    async with get_s3_client_context() as s3:
        paginator = s3.get_paginator("list_objects_v2")
        async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                objects.append(obj)
    return objects


async def get_object_content(key: str, bucket: str = None) -> bytes:
    """Download an object from S3 and return its content."""
    bucket = bucket or settings.MINIO_BUCKET_NAME
    async with get_s3_client_context() as s3:
        response = await s3.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            return await stream.read()


async def stream_object(key: str, bucket: str = None) -> AsyncGenerator[bytes, None]:
    """Stream an object from S3 in chunks."""
    bucket = bucket or settings.MINIO_BUCKET_NAME
    async with get_s3_client_context() as s3:
        response = await s3.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            while chunk := await stream.read(65536):  # 64KB chunks
                yield chunk


async def put_object(key: str, content: bytes, content_type: str = "application/json", bucket: str = None) -> None:
    """Upload content to S3."""
    bucket = bucket or settings.MINIO_BUCKET_NAME
    async with get_s3_client_context() as s3:
        await s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )


async def get_presigned_url(key: str, expiry: int = 3600, bucket: str = None) -> str:
    """Generate a presigned URL for temporary object access."""
    bucket = bucket or settings.MINIO_BUCKET_NAME
    async with get_s3_client_context() as s3:
        return await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        )
