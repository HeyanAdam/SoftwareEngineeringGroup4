"""文件存储模块的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class Result(BaseModel):
    """统一响应体外壳。

    Attributes:
        code: 业务码, 0 表示成功。
        message: 给用户看的中文提示。
        data: 业务数据, 失败时为 None。
    """

    code: int = 0
    message: str = "success"
    data: Any | None = None

class FileUploadInitRequest(BaseModel):
    """初始化分片上传会话请求。"""

    filename: str = Field(..., min_length=1, max_length=255)
    total_size: int = Field(..., gt=0)
    chunk_size: int | None = Field(default=None, gt=0)
    mime_type: str | None = Field(default=None, max_length=128)
    md5: str | None = Field(default=None, max_length=32)

class FileUploadInitData(BaseModel):
    """初始化分片上传会话返回数据。"""

    upload_id: str
    chunk_size: int
    total_chunks: int
    expire_at: str

class FileUploadPartData(BaseModel):
    """上传单个分片返回数据。"""

    upload_id: str
    chunk_index: int
    chunk_md5: str

class FileUploadProgressData(BaseModel):
    """查询上传进度返回数据。"""

    upload_id: str
    filename: str
    total_size: int
    chunk_size: int
    total_chunks: int
    uploaded_chunks: list[int]
    uploaded_count: int
    status: int
    progress: float
    expire_at: str

class FileUploadCompleteData(BaseModel):
    """完成分片上传后返回的文件信息。"""

    id: int
    object_key: str
    original_name: str
    size: int
    md5: str
    mime_type: str | None = None

class FileBatchItem(BaseModel):
    """小文件批量上传结果中的单条记录。"""

    id: int | None = None
    object_key: str | None = None
    original_name: str
    size: int | None = None
    md5: str | None = None
    mime_type: str | None = None
    skipped: bool = False
    error: str | None = None

class FileBatchUploadData(BaseModel):
    """小文件批量上传返回数据。"""

    total: int
    success: int
    failed: int
    skipped: int
    results: list[FileBatchItem]

class FileItemOut(BaseModel):
    """文件列表单条数据。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_key: str
    original_name: str
    size: int
    md5: str
    mime_type: str | None = None
    source: int
    created_at: str

class FileListData(BaseModel):
    """文件列表分页返回数据。"""

    list: list[FileItemOut]
    total: int
    page_num: int
    page_size: int

class FileDeleteData(BaseModel):
    """删除文件返回数据。"""

    ok: bool = True

class FileDownloadQuery(BaseModel):
    """断点续传下载查询参数。"""

    file_id: int | None = None
    object_key: str | None = None