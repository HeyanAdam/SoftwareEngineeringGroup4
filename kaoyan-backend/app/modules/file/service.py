"""文件存储模块业务逻辑 (本地磁盘版, 用于快速验证)。

实现 MinIO 风格的 MultipartUpload 协议 (三阶段):
    1. init_session()         ← MinIO InitiateMultipartUpload
    2. upload_part()          ← MinIO UploadPart
    3. complete_upload()      ← MinIO CompleteMultipartUpload (内部触发后台重组)

同时实现断点续传的关键能力:
    - get_progress()          ← 客户端恢复时先查已上传分片, 跳过重传
    - 后台流式重组             ← 分片合并到一个完整文件, 不占内存

存储介质: 本地磁盘 (storage/files + storage/chunks) + SQLite (FileMeta / UploadSession / UploadChunk)。
后续切回 MinIO 只需把本地读写替换为 minio_client.put_object() / get_object(), 接口层和 ORM 层不动。
"""

from __future__ import annotations

import hashlib
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
    FileMeta,
    UploadChunk,
    UploadSession,
    SESSION_STATUS_ABORTED,
    SESSION_STATUS_ASSEMBLING,
    SESSION_STATUS_DONE,
    SESSION_STATUS_FAILED,
    SESSION_STATUS_UPLOADING,
)

# ================================================================
# 本地磁盘目录 (替换 MinIO 作为存储介质)
# ================================================================
STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage"
FILE_DIR     = STORAGE_ROOT / "files"     # 最终文件存放
CHUNK_DIR    = STORAGE_ROOT / "chunks"    # 分片临时存放: chunks/{upload_id}/part-{idx:06d}
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
FILE_DIR.mkdir(parents=True, exist_ok=True)
CHUNK_DIR.mkdir(parents=True, exist_ok=True)


def _md5_of_file(path: str | Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()


def _md5_of_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _guess_mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "gif": "image/gif", "pdf": "application/pdf",
        "mp4": "video/mp4", "txt": "text/plain",
        "zip": "application/zip", "rar": "application/x-rar-compressed",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return mapping.get(ext, "application/octet-stream")


def _now_utc() -> datetime:
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


# ====================================================================
# 小文件批量写入 (作业 3.1)
# ====================================================================

class SmallFileService:
    """小文件批量写入 + MD5 秒传去重 + MinIO 落盘。"""

    MAX_BATCH_FILES = 50
    MAX_SINGLE_SIZE = 10 * 1024 * 1024   # 10 MB
    MAX_TOTAL_SIZE = 100 * 1024 * 1024   # 100 MB

    def __init__(self, db: Session) -> None:
        self.db = db

    async def batch_upload(
        self, files: list[UploadFile], user_id: int | None = None
    ) -> list[dict]:
        if not files:
            raise BadRequestError("至少需要 1 个文件")
        if len(files) > self.MAX_BATCH_FILES:
            raise BadRequestError(f"单次最多 {self.MAX_BATCH_FILES} 个文件")

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

            # 秒传: 相同 MD5 已落盘 → 直接返回已有记录
            existed = self.db.execute(
                select(FileMeta).where(FileMeta.md5 == md5)
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

            meta = FileMeta(
                object_key=rel_path,
                original_name=up.filename or rel_path,
                mime_type=content_type,
                size=size,
                md5=md5,
                user_id=user_id,
                source="small",
            )
            self.db.add(meta)
            self.db.commit()
            self.db.refresh(meta)
            return self._serialize(meta, skipped=False)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @staticmethod
    def _serialize(meta: FileMeta, skipped: bool = False) -> dict:
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

    # ---------------- 1️⃣ Init ----------------
    def init_session(
        self,
        *,
        filename: str,
        total_size: int,
        chunk_size: int | None = None,
        mime_type: str | None = None,
        md5: str | None = None,
        user_id: int | None = None,
    ) -> UploadSession:
        if total_size <= 0:
            raise BadRequestError("total_size 必须为正")

        cs = chunk_size or self.DEFAULT_CHUNK_SIZE
        if cs < self.MIN_CHUNK_SIZE:
            raise BadRequestError(f"chunk_size 不能小于 {self.MIN_CHUNK_SIZE}")

        total_chunks = max(1, -(-total_size // cs))  # ceil

        session = UploadSession(
            upload_id=uuid.uuid4().hex,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type or _guess_mime(filename),
            total_size=total_size,
            total_chunks=total_chunks,
            chunk_size=cs,
            md5=md5,
            status=SESSION_STATUS_UPLOADING,
            expire_at=_now_utc() + timedelta(hours=self.EXPIRE_HOURS),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        # MinIO 不需要预创建目录, 分片会自动在 _chunks/{upload_id}/ 前缀下生成
        return session

    # ---------------- 2️⃣ Upload Part ----------------
    def upload_part(
        self,
        upload_id: str,
        chunk_index: int,
        chunk_data: bytes,
        expected_size: int | None = None,
    ) -> UploadChunk:
        session = self._get_session(upload_id, must_status=SESSION_STATUS_UPLOADING)

        if not (0 <= chunk_index < session.total_chunks):
            raise BadRequestError(
                f"chunk_index 超出范围 [0, {session.total_chunks - 1}]"
            )

        if expected_size is not None and len(chunk_data) != expected_size:
            raise BadRequestError(
                f"分片大小不匹配: 期望 {expected_size}, 收到 {len(chunk_data)}"
            )

        # 最后一片允许比 chunk_size 小, 前面的不允许
        if chunk_index < session.total_chunks - 1 and len(chunk_data) != session.chunk_size:
            raise BadRequestError(
                f"非最后一片必须是完整 chunk_size={session.chunk_size}，"
                f"实际 {len(chunk_data)}"
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
            select(UploadChunk).where(
                UploadChunk.upload_id == upload_id,
                UploadChunk.chunk_index == chunk_index,
            )
        ).scalar_one_or_none()
        if chunk:
            chunk.chunk_size = len(chunk_data)
            chunk.chunk_md5 = chunk_md5
            chunk.stored_path = str(chunk_file)
        else:
            chunk = UploadChunk(
                upload_id=upload_id,
                chunk_index=chunk_index,
                chunk_size=len(chunk_data),
                chunk_md5=chunk_md5,
                stored_path=str(chunk_file),
            )
            self.db.add(chunk)

        # 更新 session.updated_at, 避免被清理 worker 误删
        session.updated_at = _now_utc()
        self.db.commit()
        return chunk

    # ---------------- 3️⃣ Progress (断点续传关键) ----------------
    def get_progress(self, upload_id: str) -> dict:
        session = self._get_session(upload_id)
        stmt = (
            select(UploadChunk.chunk_index)
            .where(UploadChunk.upload_id == upload_id)
            .order_by(UploadChunk.chunk_index)
        )
        indices = [r[0] for r in self.db.execute(stmt).all()]
        return {
            "upload_id": session.upload_id,
            "filename": session.filename,
            "total_size": session.total_size,
            "chunk_size": session.chunk_size,
            "total_chunks": session.total_chunks,
            "uploaded_chunks": indices,                     # 客户端据此跳过已上传
            "uploaded_count": len(indices),
            "status": session.status,
            "progress": round(len(indices) / session.total_chunks * 100, 1),
            "expire_at": session.expire_at.isoformat(),
        }

    # ---------------- 4️⃣ Complete + 后台流式重组 ----------------
    def complete_upload(self, upload_id: str) -> FileMeta | None:
        session = self._get_session(upload_id, must_status=SESSION_STATUS_UPLOADING)

        chunk_count = self.db.execute(
            select(func.count(UploadChunk.id)).where(UploadChunk.upload_id == upload_id)
        ).scalar_one() or 0
        if chunk_count < session.total_chunks:
            raise ConflictError(
                f"分片未传完 ({chunk_count}/{session.total_chunks}), "
                "请先补传剩余分片或查询进度接口查看哪些已上传"
            )

        # 标记 assembling, 防止并发 complete
        session.status = SESSION_STATUS_ASSEMBLING
        session.updated_at = _now_utc()
        self.db.commit()

        try:
            meta = self._assemble(session)
            session.status = SESSION_STATUS_DONE
            session.updated_at = _now_utc()
            session.result_file_id = meta.id
            self.db.commit()

            # 清理 MinIO 上的分片
            self._cleanup_chunks(upload_id)
            self.db.execute(
                UploadChunk.__table__.delete().where(UploadChunk.upload_id == upload_id)
            )
            self.db.commit()
            return meta
        except Exception:  # noqa: BLE001
            session.status = SESSION_STATUS_FAILED
            self.db.commit()
            raise

    def _assemble(self, session: UploadSession) -> FileMeta:
        """后台流式重组: 从本地磁盘读取分片, 流式合并到最终文件 (不占内存)。"""
        chunks = (
            self.db.execute(
                select(UploadChunk)
                .where(UploadChunk.upload_id == session.upload_id)
                .order_by(UploadChunk.chunk_index)
            ).scalars().all()
        )
        if not chunks:
            raise BadRequestError("没有可合并的分片")

        # 流式合并到临时文件, 再原子 move 到最终位置
        ext = Path(session.filename).suffix
        tmp_merged = tempfile.NamedTemporaryFile(delete=False, dir=str(STORAGE_ROOT), suffix=".bin")
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

            # 秒传: 如果重组后 MD5 与某个已落盘文件相同, 复用那条记录
            existed = self.db.execute(
                select(FileMeta).where(FileMeta.md5 == actual_md5)
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
            meta = FileMeta(
                object_key=rel_path,
                original_name=session.filename,
                mime_type=content_type,
                size=actual_size,
                md5=actual_md5,
                user_id=session.user_id,
                source="multipart",
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

    # ---------------- 5️⃣ Abort ----------------
    def abort_upload(self, upload_id: str) -> None:
        session = self._get_session(upload_id)
        self._cleanup_chunks(upload_id)
        self.db.delete(session)  # cascade 带 chunk 一起删
        self.db.commit()

    # ---------------- 内部 ----------------
    def _get_session(
        self,
        upload_id: str,
        must_status: str | None = None,
    ) -> UploadSession:
        session = self.db.execute(
            select(UploadSession).where(UploadSession.upload_id == upload_id)
        ).scalar_one_or_none()
        if session is None:
            raise NotFoundError("上传会话不存在或已过期")
        if must_status and session.status != must_status:
            raise BadRequestError(
                f"会话状态为 {session.status}, 期望 {must_status}"
            )
        return session


# ====================================================================
# 断点续传下载 (作业 3.2 读写支持断点续传)
# ====================================================================

class FileDownloadService:
    """支持 Range 头的断点续传下载 (MinIO 版)。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_meta(
        self,
        file_id: int | None = None,
        object_key: str | None = None,
        md5: str | None = None,
    ) -> FileMeta:
        stmt = select(FileMeta)
        if file_id is not None:
            stmt = stmt.where(FileMeta.id == file_id)
        elif object_key is not None:
            stmt = stmt.where(FileMeta.object_key == object_key)
        elif md5 is not None:
            stmt = stmt.where(FileMeta.md5 == md5)
        else:
            raise BadRequestError("file_id / object_key / md5 至少传一个")
        meta = self.db.execute(stmt).scalar_one_or_none()
        if meta is None:
            raise NotFoundError("文件不存在")
        return meta

    def resolve_disk_path(self, meta: FileMeta) -> str:
        """从 DB 存的相对路径解析出本地磁盘绝对路径。"""
        return str(_file_abs_path(meta.object_key))

    def list_files(
        self,
        user_id: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[FileMeta], int]:
        stmt = select(FileMeta)
        if user_id is not None:
            stmt = stmt.where(FileMeta.user_id == user_id)
        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one() or 0
        stmt = stmt.order_by(FileMeta.created_at.desc()).offset(offset).limit(limit)
        rows = list(self.db.execute(stmt).scalars().all())
        return rows, total

    def delete_file(self, file_id: int) -> None:
        meta = self.get_meta(file_id=file_id)
        # 删除本地磁盘文件
        abs_path = _file_abs_path(meta.object_key)
        try:
            if abs_path.exists():
                os.unlink(abs_path)
        except OSError:
            pass  # 文件已不存在不阻断 DB 删除
        self.db.delete(meta)
        self.db.commit()
