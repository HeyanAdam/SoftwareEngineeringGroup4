"""生成依赖与配置版本清单 (docs/VERSIONS.md)。

直接读取仓库里的真实配置来源, 不手写版本号, 避免文档与代码脱节:
    * kaoyan-frontend/package.json        前端依赖(直接/开发依赖分开)
    * kaoyan-frontend/package-lock.json   前端锁定版本(如果 lockfile 已同步)
    * kaoyan-backend/requirements.txt     后端 Python 依赖
    * docker-compose.yml                  容器镜像与端口
    * kaoyan-backend/.env.example         运行环境默认配置

用法(仓库根目录):
    python tools/gen-versions.py

新增依赖后重新跑一次即可, 输出会覆盖 docs/VERSIONS.md。
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "kaoyan-frontend"
BACKEND = ROOT / "kaoyan-backend"
OUTPUT = ROOT / "docs" / "VERSIONS.md"


# --------------------------------------------------------------------------- #
# 读取工具
# --------------------------------------------------------------------------- #
def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def installed_versions() -> dict[str, str]:
    """从 lockfile 里取出实际锁定版本: 包名 -> 版本。"""
    lock_path = FRONTEND / "package-lock.json"
    if not lock_path.exists():
        return {}
    lock = read_json(lock_path)
    result: dict[str, str] = {}
    for key, meta in (lock.get("packages") or {}).items():
        if not key.startswith("node_modules/"):
            continue
        name = key[len("node_modules/") :]
        # 跳过嵌套的 node_modules/xxx/node_modules/yyy
        if "/node_modules/" in name:
            continue
        version = meta.get("version")
        if version:
            result[name] = version
    return result


def parse_requirements(path: Path) -> list[tuple[str, str, str]]:
    """解析 requirements.txt, 返回 [(包名, 版本约束, 注释)]。"""
    items: list[tuple[str, str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        # 例如 fastapi>=0.110,<1.0  或  uvicorn[standard]>=0.27,<1.0
        match = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]+\])?\s*(.*)$", line)
        if not match:
            continue
        name, extra, constraint = match.group(1), match.group(2) or "", match.group(3).strip()
        comment = raw.split("#", 1)[1].strip() if "#" in raw else ""
        items.append((name + extra, constraint or "(未约束)", comment))
    return items


def parse_compose(path: Path) -> list[dict[str, str]]:
    """从 docker-compose.yml 提取服务名 / 镜像 / 全部端口映射 / 容器名。

    刻意不引入 yaml 依赖(离线环境装不了), 用缩进规则解析本项目这份简单文件:
      * 只在顶层 `services:` 区块内取服务(避免把 `volumes:` 下的命名卷当成服务)
      * 一个服务的多个端口映射要全部收集, 不能只留最后一个
    """
    services: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_services = False

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # 顶层区块标记(无缩进): services / volumes / networks
        top_level = re.match(r"^([a-z_]+):\s*$", line)
        if top_level:
            in_services = top_level.group(1) == "services"
            current = None
            continue

        if not in_services:
            continue

        # 服务名: 恰好两个空格缩进 + 名称 + 冒号
        service_match = re.match(r"^  ([a-z0-9_\-]+):\s*$", line)
        if service_match:
            current = {
                "name": service_match.group(1),
                "image": "-",
                "ports": "-",
                "container": "-",
            }
            services.append(current)
            continue

        if current is None:
            continue

        if stripped.startswith("image:"):
            current["image"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("container_name:"):
            current["container"] = stripped.split(":", 1)[1].strip()
        else:
            port_match = re.match(r'^-\s*"?(\d+:\d+)"?', stripped)
            if port_match:
                existing = current["ports"]
                current["ports"] = (
                    port_match.group(1) if existing == "-" else f"{existing}, {port_match.group(1)}"
                )

    return services


def parse_env_example(path: Path) -> list[tuple[str, str, str]]:
    """解析 .env.example, 返回 [(变量名, 值, 上方注释)]。

    注释里形如 `---- Redis ----` 的分隔线不算说明文字, 直接丢弃。
    """
    items: list[tuple[str, str, str]] = []
    pending_comment = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            text = line.lstrip("#").strip()
            # 分隔线注释(---- xxx ----)不作为变量说明
            if text and not re.fullmatch(r"[-=\s]*", text) and not text.startswith("----"):
                pending_comment = text
            continue
        if not line or "=" not in line:
            pending_comment = ""
            continue
        key, value = line.split("=", 1)
        items.append((key.strip(), value.strip(), pending_comment))
        pending_comment = ""
    return items


# --------------------------------------------------------------------------- #
# 生成
# --------------------------------------------------------------------------- #
def build() -> str:
    pkg = read_json(FRONTEND / "package.json")
    locked = installed_versions()

    lines: list[str] = []
    add = lines.append

    add("# 配置与依赖版本清单")
    add("")
    add("> 本文件由 `python tools/gen-versions.py` 自动生成，**请勿手工编辑**。")
    add("> 新增或升级依赖后重新执行该脚本即可刷新。")
    add("")
    add(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    add("")

    # ---------------------------------------------------------------- 总览
    add("## 1. 版本总览（照这张表装环境就不会错）")
    add("")
    add("| 组件 | 版本要求 | 说明 |")
    add("| --- | --- | --- |")
    add(
        f"| Node.js | `{pkg.get('engines', {}).get('node', '-')}` | "
        "前端 `engines` 约束，低于此版本会报 `EBADENGINE` |"
    )
    add("| npm | 随 Node 附带（10+） | 本清单按 npm 生成 |")
    add("| Python | `>=3.11` | 后端 `requirements.txt` 与语法所要求 |")
    add("| MySQL | 见第 4 节 | 容器镜像 |")
    add("| Redis | 见第 4 节 | 容器镜像 |")
    add("| MinIO | 见第 4 节 | 容器镜像 |")
    add("| Docker Desktop | 最新版（含 Compose v2） | 用于一键起基础设施 |")
    add("")

    # ---------------------------------------------------------------- 前端
    add("## 2. 前端依赖（kaoyan-frontend/package.json）")
    add("")
    add("### 2.1 运行依赖")
    add("")
    add("| 包 | 版本约束 | lockfile 锁定版本 |")
    add("| --- | --- | --- |")
    for name, spec in sorted(pkg.get("dependencies", {}).items()):
        add(f"| `{name}` | `{spec}` | `{locked.get(name, '未锁定')}` |")
    add("")
    add("### 2.2 开发依赖")
    add("")
    add("| 包 | 版本约束 | lockfile 锁定版本 |")
    add("| --- | --- | --- |")
    for name, spec in sorted(pkg.get("devDependencies", {}).items()):
        add(f"| `{name}` | `{spec}` | `{locked.get(name, '未锁定')}` |")
    add("")

    unsynced = [
        name
        for name in list(pkg.get("dependencies", {})) + list(pkg.get("devDependencies", {}))
        if name not in locked
    ]
    if unsynced:
        add("> ⚠️ **lockfile 未同步**：以下包在 `package-lock.json` 里找不到，说明 lockfile 落后于")
        add("> `package.json`。此时 **`npm ci` 会失败**，请执行 `npm install` 重建 lockfile：")
        add(">")
        add("> ```")
        add("> " + "、".join(unsynced))
        add("> ```")
        add("")

    add("### 2.3 前端脚本")
    add("")
    add("| 命令 | 实际执行 |")
    add("| --- | --- |")
    for name, cmd in pkg.get("scripts", {}).items():
        add(f"| `npm run {name}` | `{cmd}` |")
    add("")

    # ---------------------------------------------------------------- 后端
    add("## 3. 后端依赖（kaoyan-backend/requirements.txt）")
    add("")
    add("| 包 | 版本约束 | 说明 |")
    add("| --- | --- | --- |")
    for name, constraint, comment in parse_requirements(BACKEND / "requirements.txt"):
        add(f"| `{name}` | `{constraint}` | {comment or '-'} |")
    add("")
    add("安装：`pip install -r requirements.txt`")
    add("")

    # ---------------------------------------------------------------- 容器
    add("## 4. 容器镜像与端口（docker-compose.yml）")
    add("")
    add("| 服务 | 镜像 | 容器名 | 宿主机端口 → 容器端口 |")
    add("| --- | --- | --- | --- |")
    for svc in parse_compose(ROOT / "docker-compose.yml"):
        add(f"| `{svc['name']}` | `{svc['image']}` | `{svc['container']}` | `{svc['ports']}` |")
    add("")
    add("启动：`docker compose up -d`　　停止：`docker compose down`（加 `-v` 会清空数据）")
    add("")

    # ---------------------------------------------------------------- 环境变量
    add("## 5. 后端运行配置（kaoyan-backend/.env.example 默认值）")
    add("")
    add("| 变量 | 默认值 | 说明 |")
    add("| --- | --- | --- |")
    for key, value, comment in parse_env_example(BACKEND / ".env.example"):
        shown = f"`{value}`" if value else "（空）"
        add(f"| `{key}` | {shown} | {comment or '-'} |")
    add("")
    add("> 这些默认值与第 4 节的容器配置一一对应，克隆后 `copy .env.example .env` 即可直接使用。")
    add("")

    # ---------------------------------------------------------------- 自检
    add("## 6. 环境自检清单")
    add("")
    add("```powershell")
    add("node -v            # 应满足第 1 节的 Node 版本要求")
    add("python --version   # 应 >= 3.11")
    add("docker compose version")
    add("```")
    add("")
    add("| 报错关键词 | 含义 | 处理 |")
    add("| --- | --- | --- |")
    add("| `EBADENGINE` | Node 版本不满足 `engines` | 升级 Node 到第 1 节要求的版本 |")
    add("| `ERESOLVE` + `peer` | 两个包的版本约束冲突 | 对齐版本约束 |")
    add(
        "| `... in sync` / `Missing: xxx from lock file` | lockfile 与 package.json 不一致 "
        "| 用 `npm install`（**不是** `npm ci`）重建 |"
    )
    add(
        "| `ETIMEDOUT` / `ECONNRESET` | 网络问题 "
        "| `npm config set registry https://registry.npmmirror.com` |"
    )
    add("")

    return "\n".join(lines) + "\n"


def main() -> int:
    content = build()

    # --stdout: 只打印不写文件, 便于在受限环境下检查生成结果
    if "--stdout" in sys.argv:
        print(content)
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"已生成: {OUTPUT.relative_to(ROOT)}  ({len(content.splitlines())} 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
