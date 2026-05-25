"""
文件上传/下载处理工具 — MinIO 集成
"""

from minio import Minio
from minio.error import S3Error
from app.config import get_settings

settings = get_settings()


def get_minio_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


async def upload_file(file_data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
    """上传文件到 MinIO，返回文件 URL"""
    client = get_minio_client()
    bucket = settings.minio_bucket

    # 确保 bucket 存在
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=file_data,
        length=len(file_data),
        content_type=content_type,
    )
    return f"minio://{bucket}/{object_name}"


async def get_file_url(object_name: str, expires: int = 3600) -> str:
    """生成预签名下载 URL"""
    client = get_minio_client()
    return client.presigned_get_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
        expires=expires,
    )
