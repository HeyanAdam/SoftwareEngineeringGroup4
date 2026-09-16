"""Python 名字解析检查(离线替代 pyflakes/mypy)。

检查粒度是「单个文件」:
    文件里出现的每个裸名字(Load 上下文), 必须在该文件顶层有定义/导入, 或者是内置函数。

这能抓到最常见的低级错误: 拼错名字、忘了 import、用了别的文件里才有的名字、删了函数但调用还在。
而不做完整的作用域分析(那样容易误报, 反而没人看结果):
    * 函数参数、局部变量、推导式变量一律视为已定义
    * self / cls 视为已定义
    * 带 __all__ 的模块不做导出校验

用法: python tools/check_python_names.py     (仓库根目录)
"""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
TARGET_DIRS = [
    ROOT / "kaoyan-backend" / "app",
    ROOT / "kaoyan-backend" / "tools",
    ROOT / "tools",
]

SAFE_NAMES = set(dir(builtins)) | {
    "__name__",
    "__file__",
    "__doc__",
    "__package__",
    "__all__",
    "__annotations__",
    "self",
    "cls",
}


def top_level_names(tree: ast.Module) -> set[str]:
    """收集文件顶层可见的名字: 导入、函数、类、变量赋值。"""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            # 函数/lambda 参数(含嵌套函数)
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
        elif isinstance(node, ast.MatchAs) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            names.add(node.name)
    return names


def check_file(path: Path, problems: list[str]) -> None:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    known = SAFE_NAMES | top_level_names(tree)

    seen: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            continue
        if node.id in known:
            continue
        if (node.id, node.lineno) in seen:
            continue
        seen.add((node.id, node.lineno))
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        problems.append(
            f"{path.relative_to(ROOT)}:{node.lineno}: 名字 '{node.id}' 在该文件里没有定义/导入"
            f"  |  {snippet[:90]}"
        )


def main() -> int:
    problems: list[str] = []
    count = 0

    for target in TARGET_DIRS:
        if not target.exists():
            continue
        for path in sorted(target.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            count += 1
            check_file(path, problems)

    print(f"扫描 Python 文件: {count}")
    if problems:
        print(f"\n发现 {len(problems)} 处可疑名字:")
        for item in problems:
            print("  - " + item)
        return 1
    print("名字解析检查通过: 没有拼写错误或遗漏 import 的迹象 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
