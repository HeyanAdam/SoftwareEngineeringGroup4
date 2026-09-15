"""文件上传/下载接口 (MinIO)。

两种上传方式:
1. 服务端中转: POST /files/upload (multipart, 适合小文件/需要即时处理)
2. 前端直传:   POST /files/presign-upload 拿 URL -> PUT 到 MinIO -> POST /files/complete
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.core.logging import get_logger
from app.core.minio_client import put_object
from app.core.pagination import Page, PageParams, page_params
from app.schemas.common import IdResponse
from app.schemas.file import (
    FileOut,
    FileWithUrl,
    MultipartComplete,
    PresignDownloadResponse,
    PresignUploadRequest,
    PresignUploadResponse,
)
from app.services.file import FileService, build_object_name

logger = get_logger(__name__)
router = APIRouter(prefix="/files", tags=["文件管理"])


@router.get("", response_model=Page[FileOut], summary="文件分页列表")
async def list_files(
    db: DbSession,
    user: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    category: str | None = Query(default=None, max_length=48),
    keyword: str | None = Query(default=None, max_length=128),
    only_mine: bool = Query(default=False, description="只看自己上传的"),
) -> Page[FileOut]:
    # 普通用户只能看到自己的文件; 管理员可用 only_mine 缩小范围
    owner_filter = user.id if (only_mine or not user.is_superuser) else None
    rows, total = await FileService(db).list_files(
        params,
        owner_id=owner_filter,
        category=category,
        keyword=keyword,
    )
    return Page.create([FileOut.model_validate(row) for row in rows], total, params)


@router.get("/stats", summary="文件统计")
async def file_stats(db: DbSession, user: CurrentUser) -> dict[str, int]:
    return await FileService(db).stats(None if user.is_superuser else user.id)


@router.post(
    "/upload",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
    summary="服务端中转上传",
)
async def upload_file(
    db: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="待上传文件")],
    category: Annotated[str, Form()] = "attachment",
) -> FileOut:
    service = FileService(db)
    raw = await file.read()
    size = len(raw)
    service.validate_upload(file.filename or "unnamed", file.content_type or "", size)

    object_name = build_object_name(file.filename or "unnamed", category)
    await put_object(
        object_name,
        raw,
        content_type=file.content_type or "application/octet-stream",
        metadata={"uploader": user.username},
    )
    record = await service.create_record(
        object_name=object_name,
        original_name=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        size=size,
        category=category,
        owner_id=user.id,
    )
    return FileOut.model_validate(record)


@router.post("/presign-upload", response_model=PresignUploadResponse, summary="获取直传 URL")
async def presign_upload(
    payload: PresignUploadRequest, db: DbSession, _: CurrentUser
) -> PresignUploadResponse:
    data = await FileService(db).presign_upload(
        filename=payload.filename,
        content_type=payload.content_type,
        category=payload.category,
        size=payload.size,
    )
    return PresignUploadResponse(**data)  # type: ignore[arg-type]


@router.post(
    "/complete", response_model=FileOut, status_code=status.HTTP_201_CREATED, summary="直传完成登记"
)
async def complete_upload(payload: MultipartComplete, db: DbSession, user: CurrentUser) -> FileOut:
    if payload.size and payload.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise BadRequestError(f"文件超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制")
    record = await FileService(db).confirm_upload(
        object_name=payload.object_name,
        original_name=payload.original_name,
        content_type=payload.content_type,
        size=payload.size,
        category=payload.category,
        owner_id=user.id,
    )
    return FileOut.model_validate(record)


@router.get("/{file_id}", response_model=FileWithUrl, summary="文件详情 (含预签名下载地址)")
async def get_file(file_id: int, db: DbSession, user: CurrentUser) -> FileWithUrl:
    service = FileService(db)
    record = await service.get(file_id)
    url = None
    try:
        presigned = await service.presign_download(
            file_id, user_id=user.id, is_admin=user.is_superuser
        )
        url = str(presigned["url"])
    except Exception as exc:  # noqa: BLE001 详情接口容错: 存储不可用时仍返回元数据
        logger.warning("file_presign_in_detail_failed", file_id=file_id, error=str(exc))
    data = FileWithUrl.model_validate(record)
    data.url = url
    return data


@router.get("/{file_id}/download", response_model=PresignDownloadResponse, summary="获取下载地址")
async def download_file(file_id: int, db: DbSession, user: CurrentUser) -> PresignDownloadResponse:
    data = await FileService(db).presign_download(
        file_id, user_id=user.id, is_admin=user.is_superuser
    )
    return PresignDownloadResponse(**data)  # type: ignore[arg-type]


@router.delete(
    "/{file_id}",
    response_model=IdResponse,
    summary="删除文件",
    dependencies=[Depends(require_permissions("files:delete"))],
)
async def delete_file(file_id: int, db: DbSession, user: CurrentUser) -> IdResponse:
    await FileService(db).delete(file_id, user_id=user.id, is_admin=user.is_superuser)
    return IdResponse(id=file_id)
