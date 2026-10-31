"""文件下载并发压测（仅使用 Python 标准库）。

示例：
    python tools/benchmark_file_download.py --file-id 1 --concurrency 20 --requests 100
    python tools/benchmark_file_download.py --file-id 1 --concurrency 50 --requests 200 --range-bytes 1048576

输出成功率、总吞吐量以及平均/P95耗时，供课程录屏展示。
"""

from __future__ import annotations

import argparse
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def download_once(url: str, range_bytes: int | None) -> tuple[int, int, float]:
    headers = {}
    if range_bytes:
        headers["Range"] = f"bytes=0-{range_bytes - 1}"
    request = urllib.request.Request(url, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            return response.status, len(body), time.perf_counter() - started
    except urllib.error.HTTPError as exc:
        return exc.code, 0, time.perf_counter() - started
    except OSError:
        return 0, 0, time.perf_counter() - started


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * percent))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="并发下载压测")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--file-id", type=int, required=True)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--range-bytes", type=int, default=None)
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/api/file/download?file_id={args.file_id}"
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(download_once, url, args.range_bytes)
            for _ in range(args.requests)
        ]
        results = [future.result() for future in as_completed(futures)]
    elapsed = time.perf_counter() - started

    successes = [item for item in results if item[0] in (200, 206)]
    durations = [item[2] for item in successes]
    total_bytes = sum(item[1] for item in successes)
    success_rate = len(successes) / len(results) * 100 if results else 0

    print(f"URL: {url}")
    print(f"并发数/请求数: {args.concurrency}/{args.requests}")
    print(f"成功率: {success_rate:.1f}% ({len(successes)}/{len(results)})")
    print(f"总耗时: {elapsed:.3f}s")
    print(f"吞吐量: {total_bytes / max(elapsed, 0.001) / 1024 / 1024:.2f} MiB/s")
    if durations:
        print(f"平均耗时: {statistics.mean(durations):.3f}s")
        print(f"P95耗时: {percentile(durations, 0.95):.3f}s")


if __name__ == "__main__":
    main()
