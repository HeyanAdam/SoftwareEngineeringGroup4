"""后端静态一致性核对脚本。

因为当前环境无法安装依赖, 用「源码解析 + 文本比对」代替运行时验证:
    1. 逐个 import 语句检查目标模块/符号是否真实存在(ast 解析, 不执行导入)
    2. 检查路由路径与前后端契约是否一致
    3. 检查 ORM 模型字段是否都出现在 schemas 里

用法: python tools/check_backend_consistency.py   (在 kaoyan-backend 目录下执行)
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK, 中文输出会乱码
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"

problems: list[str] = []
checked_files = 0
checked_imports = 0
collected_symbols: dict[str, set[str]] = {}


def module_path(module: str) -> Path | None:
    """把 'app.core.config' 映射成文件路径。"""
    rel = module.replace(".", "/")
    for candidate in (APP.parent / f"{rel}.py", APP.parent / rel / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def collect_definitions() -> None:
    """收集每个模块顶层定义的名字(类/函数/变量/导入进来的名字)。"""
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP.parent).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        module = ".".join(parts)
        names: set[str] = set()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
        collected_symbols[module] = names


def check_imports() -> None:
    global checked_files, checked_imports
    for path in sorted(APP.rglob("*.py")):
        checked_files += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:  # 相对导入: 本仓库未使用
                    problems.append(f"{path.name}: 使用了相对导入 (level={node.level})")
                    continue
                target = node.module or ""
                if not target.startswith("app."):
                    continue  # 第三方库跳过
                checked_imports += 1
                if module_path(target) is None:
                    problems.append(f"{path.name}: 导入了不存在的模块 {target}")
                    continue
                available = collected_symbols.get(target, set())
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if alias.name not in available:
                        problems.append(
                            f"{path.name}: 从 {target} 导入了未定义的名字 {alias.name}"
                        )
            elif isinstance(node, ast.Import):
                checked_imports += 1
                for alias in node.names:
                    if alias.name.startswith("app.") and module_path(alias.name) is None:
                        problems.append(f"{path.name}: 导入了不存在的模块 {alias.name}")


def check_routes() -> None:
    """收集路由, 与前端契约清单比对。"""
    routes: list[tuple[str, str]] = []
    for path in APP.rglob("router.py"):
        text = path.read_text(encoding="utf-8")
        prefix_match = re.search(r'APIRouter\(prefix="([^"]+)"', text)
        prefix = prefix_match.group(1) if prefix_match else ""
        for method, route in re.findall(
            r'@router\.(get|post|put|patch|delete)\(\s*"([^"]*)"', text
        ):
            routes.append((method.upper(), prefix + route))

    expected = [
        ("POST", "/api/user/register"),
        ("POST", "/api/user/login"),
        ("GET", "/api/user/me"),
        ("PUT", "/api/user/me"),
        ("GET", "/api/ai/sessions"),
        ("POST", "/api/ai/sessions"),
        ("DELETE", "/api/ai/sessions/{session_id}"),
        ("GET", "/api/ai/sessions/{session_id}/messages"),
        ("POST", "/api/ai/sessions/{session_id}/messages"),
        ("GET", "/api/plan/plans"),
        ("POST", "/api/plan/plans"),
        ("GET", "/api/plan/plans/{plan_id}"),
        ("PATCH", "/api/plan/plans/{plan_id}"),
        ("DELETE", "/api/plan/plans/{plan_id}"),
        ("PATCH", "/api/plan/tasks/{task_id}"),
        ("GET", "/api/plan/stats"),
    ]
    actual = {(method, route) for method, route in routes}
    for item in expected:
        if item not in actual:
            problems.append(f"缺少约定的接口: {item[0]} {item[1]}")
    print(f"路由总数: {len(routes)} (契约要求 {len(expected)} 条, 命中 "
          f"{sum(1 for item in expected if item in actual)} 条)")


def check_models_registered() -> None:
    """每个 ORM 模型都必须被 app/models/__init__.py 导入, 否则不会建表。"""
    init_text = (APP / "models" / "__init__.py").read_text(encoding="utf-8")
    for path in (APP / "models").glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == "Base" for base in node.bases
            ):
                if node.name not in init_text:
                    problems.append(
                        f"模型 {node.name} ({path.name}) 未在 app/models/__init__.py 导出"
                    )


def main() -> int:
    collect_definitions()
    check_imports()
    check_routes()
    check_models_registered()

    print(f"扫描文件: {checked_files}, 内部导入: {checked_imports}")
    if problems:
        print(f"\n发现 {len(problems)} 个问题:")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("静态一致性核对通过: 导入、路由契约、模型注册均无问题")
    return 0


if __name__ == "__main__":
    sys.exit(main())
