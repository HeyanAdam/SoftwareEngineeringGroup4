"""文件存储模块业务逻辑 (本地磁盘版, 用于快速验证)。

实现 MinIO 风格的 MultipartUpload 协议 (三阶段):
    1. init_session()      <- MinIO InitiateMultipartUpload
    2. upload_part()       <- MinIO UploadPart
    3. complete_upload()   <- MinIO CompleteMultipartUpload (内部触发后台重组)

同时实现断点续传的关键能力:
    - get_progress()       <- 客户端恢复时先查已上传分片, 跳过重传
    - 后台流式重组        <- 分片合并到一个完整文件, 不占内存

存储介质: 本地磁盘 (storage/files + storage/chunks) + SQLite (FileMetaModel /
FileUploadSessionModel / FileUploadChunkModel)。后续切回 MinIO 只需把本地读写
替换为 minio_client.put_object() / get_object(), 接口层和 ORM 层不动。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.file import (
    FileMetaModel,
    FileSourceEnum,
    FileUploadChunkModel,
    FileUploadSessionModel,
    FileUploadStatusEnum,
)

# ================================================================
# 本地磁盘目录 (替换 MinIO 作为存储介质)
# ================================================================
STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage"
FILE_DIR = STORAGE_ROOT / "files"     # 最终文件存放
CHUNK_DIR = STORAGE_ROOT / "chunks"   # 分片临时存放: chunks/{upload_id}/part-{idx:06d}
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
FILE_DIR.mkdir(parents=True, exist_ok=True)
CHUNK_DIR.mkdir(parents=True, exist_ok=True)

def _md5_of_file(path: str | Path) -> str:
    """计算本地文件 MD5。"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()

def _md5_of_bytes(data: bytes) -> str:
    """计算字节串 MD5。"""
    return hashlib.md5(data).hexdigest()

def _sha256_of_bytes(data: bytes) -> str:
    """计算字节串 SHA-256，用于与浏览器上传前的分片摘要比较。"""
    return hashlib.sha256(data).hexdigest()

def _guess_mime(filename: str) -> str:
    """根据扩展名猜测 MIME 类型。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "pdf": "application/pdf",
        "mp4": "video/mp4",
        "txt": "text/plain",
        "zip": "application/zip",
        "rar": "application/x-rar-compressed",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return mapping.get(ext, "application/octet-stream")

def _now_utc() -> datetime:
    """返回当前 UTC 时间 (不带时区)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _chunk_file_path(upload_id: str, chunk_index: int) -> Path:
    """本地分片文件路径。"""
    return CHUNK_DIR / upload_id / f"part-{chunk_index:06d}"

def _file_rel_path(ext: str) -> str:
    """最终文件的相对路径 (存 DB 用)。"""
    return f"files/{uuid.uuid4().hex}{ext}"

def _file_abs_path(rel_path: str) -> Path:
    """从 DB 存的相对路径解析出本地绝对路径。"""
    return STORAGE_ROOT / rel_path

def _touch_modified(model: FileMetaModel | FileUploadSessionModel | FileUploadChunkModel) -> None:
    """更新 gmt_modified 通用字段。"""
    model.gmt_modified = _now_utc()

# ====================================================================
# 小文件批量写入 (作业 3.1)
# ====================================================================

class SmallFileService:
    """小文件批量写入 + MD5 秒传去重 + 本地磁盘落盘。"""

    MAX_BATCH_FILES = 50
    MAX_SINGLE_SIZE = 10 * 1024 * 1024   # 10 MB
    MAX_TOTAL_SIZE = 100 * 1024 * 1024   # 100 MB

    def __init__(self, db: Session) -> None:
        self.db = db

    async def batch_upload(
        self,
        files: list[UploadFile],
        user_id: int | None = None,
    ) -> list[dict]:
        """批量上传小文件, 支持秒传去重。

        Args:
            files: 上传文件列表。
            user_id: 上传用户 ID, 可选。

        Returns:
            每条文件的上传结果列表。

        Raises:
            BadRequestError: 文件为空或超过单次上限。
        """
        if not files:
            raise BadRequestError("至少需要 1 个文件")
        if len(files) > self.MAX_BATCH_FILES:
            raise BadRequestError(f"单次最多 {self.MAX_BATCH_FILES} 个文件")
        known_total = sum((getattr(up, "size", None) or 0) for up in files)
        if known_total > self.MAX_TOTAL_SIZE:
            raise BadRequestError(
                f"单批文件总大小不能超过 {self.MAX_TOTAL_SIZE // 1024 // 1024} MB"
            )

        results: list[dict] = []
        for up in files:
            try:
                results.append(await self._upload_one(up, user_id))
            except Exception as exc:  # noqa: BLE001 批量里某个失败不影响其他
                results.append({
                    "original_name": up.filename or "(无)",
                    "error": str(exc),
                })
        return results

    async def _upload_one(self, up: UploadFile, user_id: int | None) -> dict:
        """单个小文件落盘, 含 MD5 秒传。"""
        tmp_path = None
        try:
            # 流式读入临时文件, 算 MD5
            with tempfile.NamedTemporaryFile(delete=False, dir=str(STORAGE_ROOT)) as tmp:
                tmp_path = tmp.name
                size = 0
                while True:
                    buf = await up.read(1 << 20)   # 1 MB 流式读
                    if not buf:
                        break
                    if size + len(buf) > self.MAX_SINGLE_SIZE:
                        raise BadRequestError(
                            f"单文件超过 {self.MAX_SINGLE_SIZE // 1024 // 1024} MB, "
                            "请改走分片上传接口"
                        )
                    size += len(buf)
                    tmp.write(buf)

            md5 = _md5_of_file(tmp_path)

            # 秒传: 相同 MD5 已落盘 -> 直接返回已有记录
            existed = self.db.execute(
                select(FileMetaModel).where(
                    FileMetaModel.md5 == md5,
                    FileMetaModel.is_deleted == 0,
                )
            ).scalar_one_or_none()
            if existed:
                os.unlink(tmp_path)
                tmp_path = None
                return self._serialize(existed, skipped=True)

            # 落盘到本地磁盘
            ext = Path(up.filename or "").suffix
            rel_path = _file_rel_path(ext)
            abs_path = _file_abs_path(rel_path)
            content_type = up.content_type or _guess_mime(up.filename or "")

            abs_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp_path, str(abs_path))
            tmp_path = None  # 已移走, 不让 finally 删

            meta = FileMetaModel(
                object_key=rel_path,
                original_name=up.filename or rel_path,
                mime_type=content_type,
                size=size,
                md5=md5,
                user_id=user_id,
                source=FileSourceEnum.SMALL.value,
            )
            self.db.add(meta)
            self.db.commit()
            self.db.refresh(meta)
            return self._serialize(meta, skipped=False)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @staticmethod
    def _serialize(meta: FileMetaModel, skipped: bool = False) -> dict:
        """把 FileMetaModel 序列化为接口返回字典。"""
        return {
            "id": meta.id,
            "object_key": meta.object_key,
            "original_name": meta.original_name,
            "size": meta.size,
            "md5": meta.md5,
            "mime_type": meta.mime_type,
            "skipped": skipped,
        }

# ====================================================================
# 大文件分片上传 (作业 3.2 断点续传 + 本地分片 + 后台重组)
# ====================================================================

class MultipartService:
    """MinIO 风格 MultipartUpload 三阶段 + 断点续传。"""

    DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
    MIN_CHUNK_SIZE = 1024 * 1024          # 1 MB
    EXPIRE_HOURS = 24

    def __init__(self, db: Session) -> None:
        self.db = db

    def init_session(
        self,
        *,
        filename: str,
        total_size: int,
        chunk_size: int | None = None,
        mime_type: str | None = None,
        md5: str | None = None,
        user_id: int | None = None,
    ) -> FileUploadSessionModel:
        """初始化分片上传会话。

        Args:
            filename: 原始文件名。
            total_size: 文件总大小 (字节)。
            chunk_size: 分片大小, 默认 5 MB。
            mime_type: MIME 类型, 可选。
            md5: 整文件 MD5, 可选。
            user_id: 上传用户 ID, 可选。

        Returns:
            新建的上传会话记录。
        """
        if total_size <= 0:
            raise BadRequestError("total_size 必须为正")

        cs = chunk_size or self.DEFAULT_CHUNK_SIZE
        if cs < self.MIN_CHUNK_SIZE:
            raise BadRequestError(f"chunk_size 不能小于 {self.MIN_CHUNK_SIZE}")

        total_chunks = max(1, -(-total_size // cs))  # ceil

        session = FileUploadSessionModel(
            upload_id=uuid.uuid4().hex,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type or _guess_mime(filename),
            total_size=total_size,
            total_chunks=total_chunks,
            chunk_size=cs,
            md5=md5,
            status=FileUploadStatusEnum.UPLOADING.value,
            expire_at=_now_utc() + timedelta(hours=self.EXPIRE_HOURS),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def upload_part(
        self,
        upload_id: str,
        chunk_index: int,
        chunk_data: bytes,
        expected_size: int | None = None,
        expected_sha256: str | None = None,
    ) -> FileUploadChunkModel:
        """上传单个分片。

        Args:
            upload_id: 会话 ID。
            chunk_index: 分片序号。
            chunk_data: 分片二进制内容。
            expected_size: 期望大小, 可选。
            expected_sha256: 客户端上传前计算的 SHA-256, 用于发现损坏分片。

        Returns:
            分片记录。
        """
        session = self._get_session(upload_id, must_status=FileUploadStatusEnum.UPLOADING)

        if not (0 <= chunk_index < session.total_chunks):
            raise BadRequestError(
                f"chunk_index 超出范围 [0, {session.total_chunks - 1}]"
            )

        actual_expected_size = (
            session.chunk_size
            if chunk_index < session.total_chunks - 1
            else session.total_size - session.chunk_size * (session.total_chunks - 1)
        )
        if len(chunk_data) != actual_expected_size:
            raise BadRequestError(
                f"分片大小不匹配: 期望 {actual_expected_size}, 收到 {len(chunk_data)}"
            )
        if expected_size is not None and len(chunk_data) != expected_size:
            raise BadRequestError(
                f"客户端声明的分片大小不匹配: 期望 {expected_size}, 收到 {len(chunk_data)}"
            )

        if expected_sha256:
            actual_sha256 = _sha256_of_bytes(chunk_data)
            if not hmac.compare_digest(actual_sha256, expected_sha256.lower()):
                raise ConflictError(
                    "分片校验失败，请重传",
                    code=40901,
                    data={
                        "chunk_index": chunk_index,
                        "expected_sha256": expected_sha256.lower(),
                        "actual_sha256": actual_sha256,
                        "retryable": True,
                    },
                )

        chunk_md5 = _md5_of_bytes(chunk_data)
        chunk_file = _chunk_file_path(upload_id, chunk_index)
        chunk_file.parent.mkdir(parents=True, exist_ok=True)

        # 原子写入: 先写临时文件再 rename, 避免半片
        tmp_path = chunk_file.with_suffix(".tmp")
        with open(tmp_path, "wb") as f:
            f.write(chunk_data)
        os.replace(tmp_path, chunk_file)

        chunk = self.db.execute(
            select(FileUploadChunkModel).where(
                FileUploadChunkModel.upload_id == upload_id,
                FileUploadChunkModel.chunk_index == chunk_index,
                FileUploadChunkModel.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if chunk:
            chunk.chunk_size = len(chunk_data)
            chunk.chunk_md5 = chunk_md5
            chunk.stored_path = str(chunk_file)
            _touch_modified(chunk)
        else:
            chunk = FileUploadChunkModel(
                upload_id=upload_id,
                chunk_index=chunk_index,
                chunk_size=len(chunk_data),
                chunk_md5=chunk_md5,
                stored_path=str(chunk_file),
            )
            self.db.add(chunk)

        # 更新 session.gmt_modified, 避免被清理 worker 误删
        _touch_modified(session)
        self.db.commit()
        return chunk

    def get_progress(self, upload_id: str) -> dict:
        """查询上传进度 (断点续传关键)。

        Returns:
            包含已上传分片序号的进度信息。
        """
        session = self._get_session(upload_id)
        stmt = (
            select(FileUploadChunkModel)
            .where(
                FileUploadChunkModel.upload_id == upload_id,
                FileUploadChunkModel.is_deleted == 0,
            )
            .order_by(FileUploadChunkModel.chunk_index)
        )
        indices: list[int] = []
        invalid_indices: list[int] = []
        for chunk in self.db.execute(stmt).scalars().all():
            expected_size = (
                session.chunk_size
                if chunk.chunk_index < session.total_chunks - 1
                else session.total_size - session.chunk_size * (session.total_chunks - 1)
            )
            path = Path(chunk.stored_path)
            if (
                0 <= chunk.chunk_index < session.total_chunks
                and path.is_file()
                and path.stat().st_size == expected_size
                and _md5_of_file(path) == chunk.chunk_md5
            ):
                indices.append(chunk.chunk_index)
            else:
                invalid_indices.append(chunk.chunk_index)
        return {
            "upload_id": session.upload_id,
            "filename": session.filename,
            "total_size": session.total_size,
            "chunk_size": session.chunk_size,
            "total_chunks": session.total_chunks,
            "uploaded_chunks": indices,                     # 客户端据此跳过已上传
            "invalid_chunks": invalid_indices,              # 客户端应重传
            "uploaded_count": len(indices),
            "status": session.status,
            "progress": round(len(indices) / session.total_chunks * 100, 1),
            "expire_at": session.expire_at.isoformat(),
        }

    def complete_upload(self, upload_id: str) -> FileMetaModel | None:
        """完成上传并触发后台流式重组。

        Returns:
            落盘后的文件元数据；若 MD5 秒传命中则返回已存在记录。
        """
        session = self._get_session(upload_id, must_status=FileUploadStatusEnum.UPLOADING)

        chunks = list(self.db.execute(
            select(FileUploadChunkModel).where(
                FileUploadChunkModel.upload_id == upload_id,
                FileUploadChunkModel.is_deleted == 0,
            ).order_by(FileUploadChunkModel.chunk_index)
        ).scalars().all())
        by_index = {chunk.chunk_index: chunk for chunk in chunks}
        missing_chunks = [i for i in range(session.total_chunks) if i not in by_index]
        corrupt_chunks: list[int] = []
        for i, chunk in by_index.items():
            expected_size = (
                session.chunk_size
                if i < session.total_chunks - 1
                else session.total_size - session.chunk_size * (session.total_chunks - 1)
            )
            path = Path(chunk.stored_path)
            if (
                i < 0
                or i >= session.total_chunks
                or not path.is_file()
                or path.stat().st_size != expected_size
                or _md5_of_file(path) != chunk.chunk_md5
            ):
                corrupt_chunks.append(i)
        if missing_chunks or corrupt_chunks:
            raise ConflictError(
                "分片不完整或已损坏，请补传后重试",
                code=40902,
                data={
                    "missing_chunks": missing_chunks,
                    "corrupt_chunks": sorted(set(corrupt_chunks)),
                    "retryable": True,
                },
            )

        # 标记 assembling, 防止并发 complete
        session.status = FileUploadStatusEnum.ASSEMBLING.value
        _touch_modified(session)
        self.db.commit()

        try:
            meta = self._assemble(session)
            session.status = FileUploadStatusEnum.DONE.value
            session.result_file_id = meta.id
            _touch_modified(session)
            self.db.commit()

            # 清理本地分片和对应记录
            self._cleanup_chunks(upload_id)
            self.db.execute(
                FileUploadChunkModel.__table__.update().where(
                    FileUploadChunkModel.upload_id == upload_id
                ).values(is_deleted=1)
            )
            self.db.commit()
            return meta
        except ConflictError:
            # 整文件校验失败时保留分片并允许客户端补传。
            session.status = FileUploadStatusEnum.UPLOADING.value
            _touch_modified(session)
            self.db.commit()
            raise
        except Exception:  # noqa: BLE001
            session.status = FileUploadStatusEnum.FAILED.value
            _touch_modified(session)
            self.db.commit()
            raise

    def _assemble(self, session: FileUploadSessionModel) -> FileMetaModel:
        """后台流式重组: 从本地磁盘读取分片, 流式合并到最终文件 (不占内存)。"""
        chunks = (
            self.db.execute(
                select(FileUploadChunkModel)
                .where(
                    FileUploadChunkModel.upload_id == session.upload_id,
                    FileUploadChunkModel.is_deleted == 0,
                )
                .order_by(FileUploadChunkModel.chunk_index)
            ).scalars().all()
        )
        if not chunks:
            raise BadRequestError("没有可合并的分片")

        # 流式合并到临时文件, 再原子 move 到最终位置
        ext = Path(session.filename).suffix
        tmp_merged = tempfile.NamedTemporaryFile(
            delete=False, dir=str(STORAGE_ROOT), suffix=".bin"
        )
        tmp_merged_path = tmp_merged.name
        tmp_merged.close()

        try:
            with open(tmp_merged_path, "wb") as out:
                for c in chunks:
                    # 从本地磁盘读分片, 流式 pipe 到合并文件, 16KB buffer
                    with open(c.stored_path, "rb") as fin:
                        shutil.copyfileobj(fin, out, length=1 << 16)

            actual_size = os.path.getsize(tmp_merged_path)
            actual_md5 = _md5_of_file(tmp_merged_path)

            if actual_size != session.total_size:
                raise ConflictError(
                    f"合并后文件大小不匹配: 期望 {session.total_size}, 实际 {actual_size}",
                    code=40903,
                    data={"retryable": True},
                )
            if session.md5 and not hmac.compare_digest(actual_md5, session.md5.lower()):
                raise ConflictError(
                    "合并后整文件 MD5 校验失败",
                    code=40904,
                    data={
                        "expected_md5": session.md5.lower(),
                        "actual_md5": actual_md5,
                        "retryable": True,
                    },
                )

            # 秒传: 如果重组后 MD5 与某个已落盘文件相同, 复用那条记录
            existed = self.db.execute(
                select(FileMetaModel).where(
                    FileMetaModel.md5 == actual_md5,
                    FileMetaModel.is_deleted == 0,
                )
            ).scalar_one_or_none()
            if existed:
                os.unlink(tmp_merged_path)
                return existed

            # 落盘到本地磁盘最终位置
            rel_path = _file_rel_path(ext)
            abs_path = _file_abs_path(rel_path)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp_merged_path, str(abs_path))
            tmp_merged_path = None

            content_type = session.mime_type or _guess_mime(session.filename)
            meta = FileMetaModel(
                object_key=rel_path,
                original_name=session.filename,
                mime_type=content_type,
                size=actual_size,
                md5=actual_md5,
                user_id=session.user_id,
                source=FileSourceEnum.MULTIPART.value,
            )
            self.db.add(meta)
            self.db.commit()
            self.db.refresh(meta)
            return meta

        finally:
            if tmp_merged_path and os.path.exists(tmp_merged_path):
                os.unlink(tmp_merged_path)

    def _cleanup_chunks(self, upload_id: str) -> None:
        """清理本地磁盘上该 upload_id 的所有分片目录。"""
        chunk_dir = CHUNK_DIR / upload_id
        if chunk_dir.exists():
            shutil.rmtree(chunk_dir, ignore_errors=True)

    def abort_upload(self, upload_id: str) -> None:
        """放弃上传并清理分片和会话。"""
        session = self._get_session(upload_id)
        self._cleanup_chunks(upload_id)
        session.status = FileUploadStatusEnum.ABORTED.value
        session.is_deleted = 1
        _touch_modified(session)
        self.db.execute(
            FileUploadChunkModel.__table__.update().where(
                FileUploadChunkModel.upload_id == upload_id
            ).values(is_deleted=1)
        )
        self.db.commit()

    def _get_session(
        self,
        upload_id: str,
        must_status: FileUploadStatusEnum | None = None,
    ) -> FileUploadSessionModel:
        """按 upload_id 获取会话, 可选校验状态。"""
        session = self.db.execute(
            select(FileUploadSessionModel).where(
                FileUploadSessionModel.upload_id == upload_id,
                FileUploadSessionModel.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if session is None:
            raise NotFoundError("上传会话不存在或已过期")
        if must_status is not None and session.status != must_status.value:
            raise BadRequestError(
                f"会话状态为 {session.status}, 期望 {must_status.value}"
            )
        return session

# ====================================================================
# 断点续传下载 (作业 3.2 读写支持断点续传)
# ====================================================================

class FileDownloadService:
    """支持 Range 头的断点续传下载 (本地磁盘版)。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_meta(
        self,
        file_id: int | None = None,
        object_key: str | None = None,
        md5: str | None = None,
    ) -> FileMetaModel:
        """按 file_id / object_key / md5 查找文件元数据。"""
        stmt = select(FileMetaModel).where(FileMetaModel.is_deleted == 0)
        if file_id is not None:
            stmt = stmt.where(FileMetaModel.id == file_id)
        elif object_key is not None:
            stmt = stmt.where(FileMetaModel.object_key == object_key)
        elif md5 is not None:
            stmt = stmt.where(FileMetaModel.md5 == md5)
        else:
            raise BadRequestError("file_id / object_key / md5 至少传一个")
        meta = self.db.execute(stmt).scalar_one_or_none()
        if meta is None:
            raise NotFoundError("文件不存在")
        return meta

    def resolve_disk_path(self, meta: FileMetaModel) -> str:
        """从 DB 存的相对路径解析出本地磁盘绝对路径。"""
        return str(_file_abs_path(meta.object_key))

    def list_files(
        self,
        offset: int = 0,
        limit: int = 50,
        user_id: int | None = None,
    ) -> tuple[list[FileMetaModel], int]:
        """分页查询文件列表。

        Args:
            offset: 从第几条开始。
            limit: 最多返回多少条。
            user_id: 按用户过滤, 可选。

        Returns:
            (记录列表, 总条数)
        """
        stmt = select(FileMetaModel).where(FileMetaModel.is_deleted == 0)
        if user_id is not None:
            stmt = stmt.where(FileMetaModel.user_id == user_id)
        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one() or 0
        stmt = stmt.order_by(FileMetaModel.gmt_create.desc()).offset(offset).limit(limit)
        rows = list(self.db.execute(stmt).scalars().all())
        return rows, total

    def delete_file(self, file_id: int) -> None:
        """逻辑删除文件并清理本地磁盘。"""
        meta = self.get_meta(file_id=file_id)
        # 删除本地磁盘文件
        abs_path = _file_abs_path(meta.object_key)
        try:
            if abs_path.exists():
                os.unlink(abs_path)
        except OSError:
            pass  # 文件已不存在不阻断 DB 删除
        meta.is_deleted = 1
        _touch_modified(meta)
        self.db.commit()
