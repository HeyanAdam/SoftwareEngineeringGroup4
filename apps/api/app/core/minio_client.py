"""MinIO 对象存储封装: 桶管理 / 上传 / 预签名 URL。"""

from __future__ import annotations

import asyncio
import io
from datetime import timedelta
from functools import lru_cache
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_minio() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        region=settings.MINIO_REGION,
    )


@lru_cache
def get_minio_public() -> Minio:
    """生成预签名 URL 用的客户端 (endpoint 必须与浏览器可达地址一致)。"""
    return Minio(
        settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        region=settings.MINIO_REGION,
    )


async def _run(func, *args, **kwargs):  # noqa: ANN001, ANN202
    """minio-py 是同步库, 丢到线程池执行避免阻塞事件循环。"""
    return await asyncio.to_thread(func, *args, **kwargs)


async def ensure_bucket(bucket: str | None = None) -> None:
    name = bucket or settings.MINIO_BUCKET
    client = get_minio()

    def _ensure() -> None:
        if not client.bucket_exists(name):
            client.make_bucket(name)
            logger.info("minio_bucket_created", bucket=name)

    try:
        await asyncio.to_thread(_ensure)
    except S3Error as exc:  # pragma: no cover
        logger.error("minio_ensure_bucket_failed", bucket=name, error=str(exc))
        raise StorageError("对象存储初始化失败") from exc


async def put_object(
    object_name: str,
    data: bytes | BinaryIO,
    content_type: str = "application/octet-stream",
    *,
    bucket: str | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    name = bucket or settings.MINIO_BUCKET
    stream: BinaryIO = io.BytesIO(data) if isinstance(data, bytes) else data
    length = len(data) if isinstance(data, bytes) else _stream_length(stream)
    try:
        await _run(
            get_minio().put_object,
            name,
            object_name,
            stream,
            length,
            content_type=content_type,
            metadata=metadata,
        )
    except S3Error as exc:
        logger.error("minio_put_failed", object=object_name, error=str(exc))
        raise StorageError("文件上传失败") from exc
    return object_name


async def remove_object(object_name: str, bucket: str | None = None) -> None:
    try:
        await _run(get_minio().remove_object, bucket or settings.MINIO_BUCKET, object_name)
    except S3Error as exc:
        logger.warning("minio_remove_failed", object=object_name, error=str(exc))


async def presigned_get_url(
    object_name: str,
    *,
    expires: int | None = None,
    bucket: str | None = None,
    download_name: str | None = None,
) -> str:
    ttl = timedelta(seconds=expires or settings.MINIO_PRESIGN_EXPIRE)
    extra = (
        {"response-content-disposition": f'attachment; filename="{download_name}"'}
        if download_name
        else None
    )
    try:
        return await _run(
            get_minio_public().presigned_get_object,
            bucket or settings.MINIO_BUCKET,
            object_name,
            expires=ttl,
            response_headers=extra,
        )
    except S3Error as exc:
        logger.error("minio_presign_failed", object=object_name, error=str(exc))
        raise StorageError("生成下载链接失败") from exc


async def presigned_put_url(
    object_name: str,
    *,
    expires: int = 900,
    bucket: str | None = None,
    content_type: str = "application/octet-stream",
) -> str:
    """直传用: 前端拿到 URL 后 PUT 上传, 不经过 API 进程。"""
    try:
        return await _run(
            get_minio_public().presigned_put_object,
            bucket or settings.MINIO_BUCKET,
            object_name,
            expires=timedelta(seconds=expires),
            content_type=content_type,
        )
    except S3Error as exc:
        raise StorageError("生成上传链接失败") from exc


async def stat_object(object_name: str, bucket: str | None = None) -> dict | None:
    try:
        info = await _run(get_minio().stat_object, bucket or settings.MINIO_BUCKET, object_name)
    except S3Error:
        return None
    return {"size": info.size, "content_type": info.content_type, "etag": info.etag}


def _stream_length(stream: BinaryIO) -> int:
    pos = stream.tell()
    stream.seek(0, io.SEEK_END)
    size = stream.tell()
    stream.seek(pos)
    return size
