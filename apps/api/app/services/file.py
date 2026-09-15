"""文件元数据服务。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError, PayloadTooLargeError
from app.core.logging import get_logger
from app.core.minio_client import presigned_get_url, presigned_put_url, remove_object, stat_object
from app.core.pagination import PageParams
from app.models.file import StoredFile

logger = get_logger(__name__)

SAFE_EXT_MAX = 12


def build_object_name(original_name: str, category: str = "attachment") -> str:
    """生成不可猜测的对象 key: category/YYYY/MM/uuid.ext"""
    suffix = PurePosixPath(original_name).suffix.lower()
    if len(suffix) > SAFE_EXT_MAX or not suffix.replace(".", "").isalnum():
        suffix = ""
    now = datetime.now(UTC)
    return f"{category}/{now:%Y/%m}/{uuid.uuid4().hex}{suffix}"


class FileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    def validate_upload(self, filename: str, content_type: str, size: int | None) -> None:
        if not filename or "/" in filename or "\\" in filename:
            raise BadRequestError("文件名不合法")
        if size is not None and size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise PayloadTooLargeError(f"文件超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制")
        allowed = settings.allowed_upload_type_set
        if allowed and content_type.lower() not in allowed:
            raise BadRequestError(f"不支持的文件类型: {content_type}")

    def _base_query(self) -> Select[tuple[StoredFile]]:
        return select(StoredFile)

    async def list_files(
        self,
        params: PageParams,
        *,
        owner_id: int | None = None,
        category: str | None = None,
        keyword: str | None = None,
        only_mine: int | None = None,
    ) -> tuple[list[StoredFile], int]:
        stmt = self._base_query()
        if only_mine is not None:
            stmt = stmt.where(StoredFile.owner_id == only_mine)
        elif owner_id is not None:
            stmt = stmt.where(StoredFile.owner_id == owner_id)
        if category:
            stmt = stmt.where(StoredFile.category == category)
        if keyword:
            stmt = stmt.where(StoredFile.original_name.like(f"%{keyword.strip()}%"))

        total = (
            await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
        ).scalar_one()
        stmt = stmt.order_by(StoredFile.created_at.desc()).offset(params.offset).limit(params.limit)
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(rows), int(total)

    async def get(self, file_id: int) -> StoredFile:
        record = await self.db.get(StoredFile, file_id)
        if record is None:
            raise NotFoundError("文件不存在")
        return record

    async def get_by_object_name(self, object_name: str) -> StoredFile | None:
        return (
            await self.db.execute(select(StoredFile).where(StoredFile.object_name == object_name))
        ).scalar_one_or_none()

    async def create_record(
        self,
        *,
        object_name: str,
        original_name: str,
        content_type: str,
        size: int,
        category: str = "attachment",
        owner_id: int | None = None,
        etag: str | None = None,
        bucket: str | None = None,
        status: str = "ready",
    ) -> StoredFile:
        record = StoredFile(
            object_name=object_name,
            bucket=bucket or settings.MINIO_BUCKET,
            original_name=original_name,
            content_type=content_type,
            size=size,
            category=category,
            owner_id=owner_id,
            etag=etag,
            status=status,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        logger.info("file_record_created", file_id=record.id, object_name=object_name, size=size)
        return record

    async def presign_upload(
        self, *, filename: str, content_type: str, category: str, size: int | None
    ) -> dict[str, object]:
        self.validate_upload(filename, content_type, size)
        object_name = build_object_name(filename, category)
        url = await presigned_put_url(
            object_name, content_type=content_type, bucket=settings.MINIO_BUCKET
        )
        return {
            "upload_url": url,
            "object_name": object_name,
            "bucket": settings.MINIO_BUCKET,
            "expires_in": 900,
        }

    async def presign_download(
        self, file_id: int, *, user_id: int, is_admin: bool
    ) -> dict[str, object]:
        record = await self.get(file_id)
        if record.owner_id not in (None, user_id) and not is_admin:
            raise ForbiddenError("无权访问该文件")
        url = await presigned_get_url(record.object_name, bucket=record.bucket)
        return {
            "url": url,
            "expires_in": settings.MINIO_PRESIGN_EXPIRE,
            "original_name": record.original_name,
        }

    async def delete(self, file_id: int, *, user_id: int, is_admin: bool) -> None:
        record = await self.get(file_id)
        if record.owner_id not in (None, user_id) and not is_admin:
            raise ForbiddenError("无权删除该文件")
        await remove_object(record.object_name, record.bucket)
        await self.db.delete(record)
        await self.db.commit()
        logger.info("file_deleted", file_id=file_id, object_name=record.object_name)

    async def confirm_upload(
        self,
        *,
        object_name: str,
        original_name: str,
        content_type: str,
        size: int,
        category: str,
        owner_id: int | None,
    ) -> StoredFile:
        """直传完成后由前端调用, 校验对象确实存在再落库。"""
        existing = await self.get_by_object_name(object_name)
        if existing is not None:
            return existing
        info = await stat_object(object_name)
        if info is None:
            raise NotFoundError(f"对象存储中不存在: {object_name}")
        return await self.create_record(
            object_name=object_name,
            original_name=original_name,
            content_type=content_type or info.get("content_type") or "application/octet-stream",
            size=size or int(info.get("size") or 0),
            category=category,
            owner_id=owner_id,
            etag=info.get("etag"),
        )

    async def stats(self, owner_id: int | None = None) -> dict[str, int]:
        stmt = select(func.count(), func.coalesce(func.sum(StoredFile.size), 0))
        if owner_id is not None:
            stmt = stmt.where(StoredFile.owner_id == owner_id)
        count, total_size = (await self.db.execute(stmt)).one()
        return {"files": int(count), "bytes": int(total_size or 0)}
