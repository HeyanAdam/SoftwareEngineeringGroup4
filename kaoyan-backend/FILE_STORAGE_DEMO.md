# 文件上传下载录屏提纲

## 启动

```bash
copy .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

打开 `http://127.0.0.1:8001/static/file_test.html`。

如果旧版本已经生成过 `app_local.db`，旧表不会被 `create_all()` 自动修改。测试数据不需要保留时可先备份并删除该数据库，再启动一次；需要保留时应使用 Alembic 迁移主键类型。

## 建议录屏顺序

1. **小文件批量上传**：一次选择 3～5 个文件，展示单文件限制、批量结果和 MD5 去重。再次上传同一文件，说明相同内容不重复落盘。
2. **大文件分片与损坏重传**：选择大于 10 MB 的文件、分片设为 5 MB，勾选“模拟首片损坏”。页面第一次发送错误 SHA-256，服务端返回 `40901` 和分片序号，前端自动使用正确摘要重传。讲解 `file.slice()`、临时分片目录以及按序流式重组。
3. **上传断点续传**：上传若干分片后点击“暂停”，刷新页面，重新选择相同文件并点击“开始/继续”。讲解浏览器保存的 `upload_id`、`GET /progress/{upload_id}` 和跳过已完成分片。
4. **进度条**：指出上传进度由 `XMLHttpRequest.upload.onprogress` 按字节计算，不只是分片个数；页面同时显示已传大小和速度。
5. **下载断点续传**：开始下载后点击“暂停”，再点击“继续”。讲解客户端保存已接收字节数，继续时发送 `Range: bytes=N-` 和 `If-Range`，服务端返回 `206`、`Content-Range` 和 `ETag`。
6. **高并发下载**：运行压测脚本并展示成功率、吞吐量、平均耗时和 P95：

   ```bash
   python tools/benchmark_file_download.py --file-id 1 --concurrency 20 --requests 100
   python tools/benchmark_file_download.py --file-id 1 --concurrency 50 --requests 200 --range-bytes 1048576
   ```

## 代码讲解重点

- 每个分片上传前由浏览器计算 SHA-256，后端重新计算；不一致不落盘，并明确返回需重传的 `chunk_index`。
- `complete` 在合并前复核分片是否缺失、磁盘文件大小和 MD5；合并后再次校验整文件大小及可选整文件 MD5。
- 合并通过 64 KB 缓冲区顺序复制到临时文件，再原子移动，不把整个大文件加载到内存。
- 小文件接口使用一个 multipart/form-data 请求携带多个同名 `files` 字段，单文件失败不影响批次内其他文件。
- 本地演示版使用 SQLite + 本地磁盘。高并发基础是异步流式 Range 读取；正式部署应改为 MySQL + MinIO，并使用预签名地址、Nginx `sendfile/X-Accel-Redirect` 或 CDN 承担数据传输。

## 验证

```bash
python tools/smoke_test_file_storage.py
python tools/check_backend_consistency.py
```

冒烟测试会验证 SQLite 自增主键、客户端摘要校验、磁盘分片损坏识别、补传、重组内容以及文件列表分页。
