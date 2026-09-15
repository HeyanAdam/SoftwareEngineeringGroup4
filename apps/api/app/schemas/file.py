"""文件与对象存储 Schema。"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ORMModel, TimestampedOut


class FileOut(TimestampedOut):
    id: int
    object_name: str
    bucket: str
    original_name: str
    content_type: str
    size: int
    category: str
    status: str
    owner_id: int | None = None


class FileWithUrl(FileOut):
    url: str | None = Field(default=None, description="预签名下载地址")


class PresignUploadRequest(ORMModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=128)
    category: str = Field(default="attachment", max_length=48)
    size: int | None = Field(default=None, ge=0, description="字节数, 用于前置校验")


class PresignUploadResponse(ORMModel):
    upload_url: str
    object_name: str
    bucket: str
    expires_in: int


class PresignDownloadResponse(ORMModel):
    url: str
    expires_in: int
    original_name: str


class MultipartComplete(ORMModel):
    object_name: str
    original_name: str
    content_type: str = "application/octet-stream"
    size: int = 0
    category: str = "attachment"
