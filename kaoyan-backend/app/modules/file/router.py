"""文件存储模块接口: 小文件批量 / 大文件分片 / 断点续传。

对齐 MinIO MultipartUpload 三阶段:
    POST /init      初始化会话
    POST /part      上传单个分片
    GET  /progress  查询已上传分片 (断点续传关键)
    POST /complete  触发后台流式重组
    DELETE /abort   放弃上传

额外:
    POST /batch     小文件批量写入 (作业 3.1)
    GET  /download  断点续传下载 (作业 3.2)
    GET  /list      文件列表
    DELETE /{id}    删除文件
"""

from __future__ import annotations

import re
from urllib.parse import quote


from fastapi import APIRouter, File, HTTPException, Header, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.deps import DbSession
from app.modules.file.service import (
    FileDownloadService,
    MultipartService,
    SmallFileService,
)

router = APIRouter(prefix="/api/file", tags=["文件存储"])


def _parse_single_range(value: str, file_size: int) -> tuple[int, int]:
    """解析单段 HTTP bytes Range；不支持多段 Range。"""
    if file_size <= 0:
        raise ValueError("空文件没有可用字节范围")
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match or (not match.group(1) and not match.group(2)):
        raise ValueError("Range 格式错误")
    start_s, end_s = match.group(1), match.group(2)
    if start_s:
        start = int(start_s)
        end = min(int(end_s), file_size - 1) if end_s else file_size - 1
    else:
        suffix_length = int(end_s)
        if suffix_length <= 0:
            raise ValueError("Range 后缀长度必须为正")
        suffix_length = min(suffix_length, file_size)
        start, end = file_size - suffix_length, file_size - 1
    if start >= file_size or end < start:
        raise ValueError("Range 超出范围")
    return start, end


# ====================================================================
# 小文件批量写入 (作业 3.1)
# ====================================================================

@router.post(
    "/batch",
    summary="小文件批量上传",
    description=f"一次性上传多个小文件 (最多 {SmallFileService.MAX_BATCH_FILES} 个, 单文件 ≤ 10 MB), 支持 MD5 秒传去重。",
)
async def batch_upload(
    db: DbSession,
    files: list[UploadFile] = File(..., description="文件列表, 字段名 files"),
) -> dict:
    results = await SmallFileService(db).batch_upload(files)
    success = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    return {
        "total": len(results),
        "success": len(success),
        "failed": len(failed),
        "skipped": sum(1 for r in success if r.get("skipped")),
        "results": results,
    }


# ====================================================================
# 大文件分片上传三阶段 (作业 3.2 断点续传 + 分片 + 后台重组)
# ====================================================================

class InitRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    total_size: int = Field(..., gt=0)
    chunk_size: int | None = None
    mime_type: str | None = None
    md5: str | None = None


@router.post("/init", summary="初始化分片会话 (MinIO InitiateMultipartUpload)")
def init_multipart(payload: InitRequest, db: DbSession) -> dict:
    sess = MultipartService(db).init_session(
        filename=payload.filename,
        total_size=payload.total_size,
        chunk_size=payload.chunk_size,
        mime_type=payload.mime_type,
        md5=payload.md5,
    )
    return {
        "upload_id": sess.upload_id,
        "chunk_size": sess.chunk_size,
        "total_chunks": sess.total_chunks,
        "expire_at": sess.expire_at.isoformat(),
    }


@router.post(
    "/part",
    summary="上传单个分片 (MinIO UploadPart)",
    description="请求体放分片二进制; query 带 upload_id 和 chunk_index。",
)
async def upload_part(
    db: DbSession,
    upload_id: str = Query(...),
    chunk_index: int = Query(..., ge=0),
    chunk_sha256: str | None = Query(default=None, min_length=64, max_length=64),
    chunk: UploadFile = File(...),
) -> dict:
    data = await chunk.read()
    c = MultipartService(db).upload_part(
        upload_id=upload_id,
        chunk_index=chunk_index,
        chunk_data=data,
        expected_size=len(data),
        expected_sha256=chunk_sha256,
    )
    return {"upload_id": upload_id, "chunk_index": chunk_index, "chunk_md5": c.chunk_md5}


@router.get(
    "/progress/{upload_id}",
    summary="查询上传进度 (断点续传关键)",
    description="客户端恢复前调此接口, 根据 uploaded_chunks 跳过已上传分片。",
)
def get_progress(upload_id: str, db: DbSession) -> dict:
    return MultipartService(db).get_progress(upload_id)


@router.post(
    "/complete/{upload_id}",
    summary="完成上传并触发后台流式重组 (MinIO CompleteMultipartUpload)",
)
def complete_upload(upload_id: str, db: DbSession) -> dict:
    meta = MultipartService(db).complete_upload(upload_id)
    return {
        "assembled": True,
        "file": {
            "id": meta.id,
            "object_key": meta.object_key,
            "original_name": meta.original_name,
            "size": meta.size,
            "md5": meta.md5,
            "mime_type": meta.mime_type,
        },
    }


@router.delete("/abort/{upload_id}", summary="放弃上传并清理分片")
def abort_upload(upload_id: str, db: DbSession) -> dict:
    MultipartService(db).abort_upload(upload_id)
    return {"ok": True}


# ====================================================================
# 断点续传下载 (作业 3.2)
# ====================================================================

@router.get(
    "/download",
    summary="断点续传下载 (支持 Range 头)",
    description="传 Range: bytes=start-end → HTTP 206 + Content-Range, 否则全量。",
)
async def download(
    db: DbSession,
    file_id: int | None = Query(default=None),
    object_key: str | None = Query(default=None),
    range_header: str | None = Header(default=None, alias="Range"),
    if_range: str | None = Header(default=None, alias="If-Range"),
):
    svc = FileDownloadService(db)
    meta = svc.get_meta(file_id=file_id, object_key=object_key)
    # 直接从本地磁盘路径返回 (SQLite + 本地磁盘版)
    path_str = svc.resolve_disk_path(meta)
    import os as _os
    if not _os.path.exists(path_str):
        raise HTTPException(status_code=410, detail="文件已丢失")

    file_size = _os.path.getsize(path_str)
    etag = f'"{meta.md5}"'

    # If-Range 不匹配说明客户端持有的是旧文件片段，应退化为完整下载。
    if range_header and if_range and if_range != etag:
        range_header = None

    if not range_header:
        return FileResponse(
            path=path_str,
            media_type=meta.mime_type or "application/octet-stream",
            filename=meta.original_name,
            headers={"Accept-Ranges": "bytes", "ETag": etag},
        )

    try:
        start, end = _parse_single_range(range_header, file_size)
    except ValueError as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=416,
            content={"detail": str(exc)},
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    length = end - start + 1
    fallback_name = re.sub(r'[^A-Za-z0-9._-]', "_", meta.original_name) or "download"
    disposition = (
        f'attachment; filename="{fallback_name}"; '
        f"filename*=UTF-8''{quote(meta.original_name, safe='')}"
    )

    async def _stream():
        import aiofiles
        async with aiofiles.open(path_str, "rb") as f:
            await f.seek(start)
            remaining = length
            while remaining > 0:
                c = await f.read(min(1 << 16, remaining))
                if not c:
                    break
                remaining -= len(c)
                yield c

    return StreamingResponse(
        _stream(),
        status_code=206,
        media_type=meta.mime_type or "application/octet-stream",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
            "Content-Disposition": disposition,
            "ETag": etag,
        },
    )


# ====================================================================
# 文件列表 / 删除
# ====================================================================

@router.get("/list", summary="文件列表 (分页)")
def list_files(
    db: DbSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    rows, total = FileDownloadService(db).list_files(offset=offset, limit=limit)
    return {
        "total": total, "offset": offset, "limit": limit,
        "list": [
            {
                "id": r.id, "object_key": r.object_key,
                "original_name": r.original_name, "size": r.size,
                "md5": r.md5, "mime_type": r.mime_type,
                "source": r.source, "created_at": r.gmt_create.isoformat(),
            }
            for r in rows
        ],
    }


@router.delete("/{file_id}", summary="删除文件")
def delete_file(file_id: int, db: DbSession) -> dict:
    FileDownloadService(db).delete_file(file_id)
    return {"ok": True}
