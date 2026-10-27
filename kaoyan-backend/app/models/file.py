"""文件存储相关 ORM 模型。

包含三类实体:
    - FileUploadSessionModel: 大文件分片上传会话(断点续传核心)
    - FileUploadChunkModel: 单个分片记录
    - FileMetaModel: 已落盘文件元数据

状态与来源使用 IntEnum 映射到 TINYINT, 符合附录 A 枚举约定。
"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class FileUploadStatusEnum(IntEnum):
    """分片上传会话状态枚举。"""

    UPLOADING = 0
    ASSEMBLING = 1
    DONE = 2
    FAILED = 3
    ABORTED = 4

class FileSourceEnum(IntEnum):
    """文件来源枚举。"""

    SMALL = 0
    MULTIPART = 1

class FileUploadSessionModel(Base):
    """大文件分片上传会话模型。"""

    __tablename__ = "file_upload_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    md5: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=FileUploadStatusEnum.UPLOADING.value,
    )
    expire_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    result_file_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # 通用字段
    gmt_create: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    gmt_modified: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

class FileUploadChunkModel(Base):
    """分片上传记录模型。"""

    __tablename__ = "file_upload_chunk"
    __table_args__ = (
        UniqueConstraint("upload_id", "chunk_index", name="uq_file_upload_chunk_upload_id_index"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_md5: Mapped[str] = mapped_column(String(32), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # 通用字段
    gmt_create: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    gmt_modified: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

class FileMetaModel(Base):
    """已落盘文件元数据模型。"""

    __tablename__ = "file_meta"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    md5: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    source: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=FileSourceEnum.SMALL.value,
    )

    # 通用字段
    gmt_create: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    gmt_modified: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)