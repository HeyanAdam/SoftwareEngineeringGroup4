"""SQLite + 本地磁盘文件模块冒烟测试，不依赖 pytest。"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.exceptions import ConflictError
from app.models.file import FileMetaModel  # noqa: F401 注册模型
from app.modules.file import service
from app.modules.file.router import _parse_single_range


def main() -> None:
    assert _parse_single_range("bytes=0-4", 10) == (0, 4)
    assert _parse_single_range("bytes=5-", 10) == (5, 9)
    assert _parse_single_range("bytes=-3", 10) == (7, 9)
    try:
        _parse_single_range("bytes=8-2", 10)
    except ValueError:
        pass
    else:
        raise AssertionError("非法 Range 未被拒绝")

    # 指定项目当前目录，兼容限制系统临时目录写入的沙盒/CI 环境。
    with tempfile.TemporaryDirectory(prefix="file-storage-smoke-", dir=Path.cwd()) as temp:
        root = Path(temp)
        service.STORAGE_ROOT = root
        service.FILE_DIR = root / "files"
        service.CHUNK_DIR = root / "chunks"
        service.FILE_DIR.mkdir()
        service.CHUNK_DIR.mkdir()

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        payload = os.urandom(1024 * 1024 + 321)
        chunk_size = 1024 * 1024

        with Session(engine, expire_on_commit=False) as db:
            multipart = service.MultipartService(db)
            upload = multipart.init_session(
                filename="smoke.bin",
                total_size=len(payload),
                chunk_size=chunk_size,
            )
            first = payload[:chunk_size]
            second = payload[chunk_size:]
            multipart.upload_part(
                upload.upload_id,
                0,
                first,
                expected_sha256=hashlib.sha256(first).hexdigest(),
            )

            try:
                multipart.upload_part(
                    upload.upload_id,
                    1,
                    second,
                    expected_sha256="0" * 64,
                )
            except ConflictError as exc:
                assert exc.code == 40901
                assert exc.data["chunk_index"] == 1
            else:
                raise AssertionError("损坏摘要没有被拒绝")

            multipart.upload_part(
                upload.upload_id,
                1,
                second,
                expected_sha256=hashlib.sha256(second).hexdigest(),
            )
            assert multipart.get_progress(upload.upload_id)["uploaded_count"] == 2

            # 模拟分片落盘后损坏：进度接口和 complete 都必须指出第 1 片需重传。
            (service.CHUNK_DIR / upload.upload_id / "part-000001").write_bytes(b"broken")
            progress = multipart.get_progress(upload.upload_id)
            assert progress["uploaded_chunks"] == [0]
            assert progress["invalid_chunks"] == [1]
            try:
                multipart.complete_upload(upload.upload_id)
            except ConflictError as exc:
                assert exc.code == 40902
                assert exc.data["corrupt_chunks"] == [1]
            else:
                raise AssertionError("损坏分片没有阻止重组")
            multipart.upload_part(
                upload.upload_id,
                1,
                second,
                expected_sha256=hashlib.sha256(second).hexdigest(),
            )
            meta = multipart.complete_upload(upload.upload_id)
            assert meta.id is not None, "SQLite 自增主键失败"
            assert meta.size == len(payload)
            assert Path(service._file_abs_path(meta.object_key)).read_bytes() == payload

            rows, total = service.FileDownloadService(db).list_files(offset=0, limit=10)
            assert total == 1 and rows[0].id == meta.id

    print("file storage smoke test: PASS")


if __name__ == "__main__":
    main()
