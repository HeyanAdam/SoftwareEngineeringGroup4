"""文件存储相关模型: 上传会话、分片、已落盘文件元数据。

协议对齐 MinIO MultipartUpload:
    UploadSession  ← MinIO InitiateMultipartUpload
    UploadChunk    ← MinIO UploadPart
    FileMeta       ← MinIO ListObjects
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

SESSION_STATUS_UPLOADING = "uploading"
SESSION_STATUS_ASSEMBLING = "assembling"
SESSION_STATUS_DONE = "done"
SESSION_STATUS_FAILED = "failed"
SESSION_STATUS_ABORTED = "aborted"


class UploadSession(Base):
    """大文件分片上传会话 (断点续传核心)."""
    __tablename__ = "upload_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    md5: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SESSION_STATUS_UPLOADING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expire_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    result_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chunks: Mapped[list["UploadChunk"]] = relationship(
        "UploadChunk", back_populates="session", cascade="all, delete-orphan"
    )


class UploadChunk(Base):
    """单个分片. 同一个 (upload_id, chunk_index) 唯一."""
    __tablename__ = "upload_chunks"
    __table_args__ = (UniqueConstraint("upload_id", "chunk_index", name="uq_session_chunk"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("upload_sessions.upload_id"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_md5: Mapped[str] = mapped_column(String(32), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[UploadSession] = relationship("UploadSession", back_populates="chunks")


class FileMeta(Base):
    """已落盘文件元数据 (小文件直接落盘, 大文件由 UploadSession 重组后落盘)."""
    __tablename__ = "file_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    md5: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="small")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
