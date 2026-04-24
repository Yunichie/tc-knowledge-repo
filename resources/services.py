import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings


def get_r2_client():
    """Returns a configured boto3 S3 client for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def generate_presigned_put(filename: str, content_type: str) -> dict:
    """
    Generates a presigned PUT URL with a 1hr expiry.
    (Note: R2 does not support POST policies, so we must use PUT. Size limits 
    will need to be enforced client-side or validated post-upload).
    """
    client = get_r2_client()

    # Generate unique object key to prevent collisions
    ext = filename.split(".")[-1] if "." in filename else ""
    object_key = f"resources/{uuid.uuid4()}.{ext}"

    try:
        url = client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": settings.R2_BUCKET_NAME,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=settings.R2_PRESIGNED_URL_EXPIRY,
        )
        return {
            "url": url,
            "object_key": object_key,
        }
    except ClientError as e:
        raise Exception(f"Could not generate presigned PUT URL: {str(e)}")


def generate_presigned_get(object_key: str, expires_in: int = 3600) -> str:
    """
    Generates a presigned GET URL for downloads.
    """
    client = get_r2_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.R2_BUCKET_NAME,
                "Key": object_key,
            },
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        raise Exception(f"Could not generate presigned GET URL: {str(e)}")


def stream_object(object_key: str, chunk_size: int = 8192):
    """
    Yields chunks from an R2 object.
    """
    client = get_r2_client()
    try:
        response = client.get_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=object_key,
        )
        body = response["Body"]
        for chunk in body.iter_chunks(chunk_size=chunk_size):
            if chunk:
                yield chunk
    except ClientError as e:
        raise Exception(f"Could not stream object {object_key}: {str(e)}")
