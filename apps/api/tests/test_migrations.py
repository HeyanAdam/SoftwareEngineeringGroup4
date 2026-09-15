"""Alembic 迁移结构校验。

用 `alembic upgrade head --sql` 离线渲染 MySQL DDL (CI 里的同一动作, 不需要数据库),
再与 ORM 元数据逐表逐列比对: 列名/类型/可空性/默认值/索引/唯一约束/外键 ondelete。

注: 迁移是面向 MySQL 的 (created_at 使用 `DEFAULT now()`), 因此这里不落到 SQLite 执行。
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import mysql

import app.models  # noqa: F401  确保所有表注册进 Base.metadata
from alembic import command
from app.core.database import Base

API_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = API_DIR / "alembic.ini"
INITIAL_REVISION = "0001_initial_schema"
MYSQL_URL = "mysql+pymysql://sg4:sg4@127.0.0.1:3306/sg4_test?charset=utf8mb4"

EXPECTED_TABLES = (
    "users",
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "stored_files",
    "chat_rooms",
    "chat_messages",
    "daily_stats",
)

_SQL_CACHE: dict[str, str] = {}


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    return config


def _offline_upgrade_sql(monkeypatch: pytest.MonkeyPatch) -> str:
    if "sql" not in _SQL_CACHE:
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", MYSQL_URL)
        config = _alembic_config()
        buffer = io.StringIO()
        config.output_buffer = buffer
        command.upgrade(config, "head", sql=True)
        _SQL_CACHE["sql"] = buffer.getvalue()
    return _SQL_CACHE["sql"]


def _table_body(sql: str, table: str) -> str:
    match = re.search(rf"CREATE TABLE {re.escape(table)} \((.*?)\n\)", sql, re.S)
    assert match, f"迁移里缺少 CREATE TABLE {table}"
    return match.group(1)


def _column_line(body: str, column: str) -> str | None:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if re.match(rf"^{re.escape(column)}\s", line):
            return line
    return None


def test_single_head_revision() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert script.get_heads() == [INITIAL_REVISION]
    revisions = list(script.walk_revisions())
    assert len(revisions) == 1
    assert revisions[0].down_revision is None


def test_offline_sql_creates_exactly_the_model_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sql = _offline_upgrade_sql(monkeypatch)
    created = set(re.findall(r"CREATE TABLE (\w+)", sql))
    created.discard("alembic_version")  # alembic 自己维护的版本表

    assert sorted(created) == sorted(EXPECTED_TABLES)
    assert sorted(Base.metadata.tables) == sorted(EXPECTED_TABLES)


def test_columns_types_nullability_and_defaults_match_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sql = _offline_upgrade_sql(monkeypatch)
    dialect = mysql.dialect()

    for table in Base.metadata.sorted_tables:
        body = _table_body(sql, table.name)
        assert "PRIMARY KEY (" in body, table.name

        for column in table.columns:
            line = _column_line(body, column.name)
            assert line is not None, f"{table.name}.{column.name} 未出现在迁移中"

            expected_type = column.type.compile(dialect=dialect).upper()
            assert line.upper().startswith(f"{column.name.upper()} {expected_type}"), (
                table.name,
                line,
                expected_type,
            )
            assert ("NOT NULL" in line.upper()) is (not column.nullable), (table.name, line)

            if column.server_default is not None:
                assert "DEFAULT now()" in line, (table.name, line)


def test_indexes_unique_constraints_and_foreign_keys_match_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sql = _offline_upgrade_sql(monkeypatch)

    for table in Base.metadata.sorted_tables:
        body = _table_body(sql, table.name)
        upper_body = body.upper()

        for index in table.indexes:
            assert f"CREATE INDEX {index.name} ON {table.name}" in sql, index.name
            if index.unique:
                first_column = next(iter(index.columns)).name
                assert f"uq_{table.name}_{first_column}" in body, index.name

        for constraint in table.constraints:
            if isinstance(constraint, sa.UniqueConstraint):
                assert f"CONSTRAINT {constraint.name} UNIQUE" in body, constraint.name

        for foreign_key in table.foreign_keys:
            name = foreign_key.constraint.name
            assert f"CONSTRAINT {name} FOREIGN KEY" in body, name
            if foreign_key.constraint.ondelete:
                rule = foreign_key.constraint.ondelete.upper()
                assert f"ON DELETE {rule}" in upper_body, (name, rule)


def test_migration_sets_mysql_bigint_and_varchar_lengths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sql = _offline_upgrade_sql(monkeypatch)

    assert "size BIGINT NOT NULL" in _table_body(sql, "stored_files")
    assert "value BIGINT NOT NULL" in _table_body(sql, "daily_stats")
    assert "email VARCHAR(191) NOT NULL" in _table_body(sql, "users")
    assert "object_name VARCHAR(512) NOT NULL" in _table_body(sql, "stored_files")
    assert "content TEXT NOT NULL" in _table_body(sql, "chat_messages")
    assert "stat_date DATE NOT NULL" in _table_body(sql, "daily_stats")
    assert "ON DELETE SET NULL" in sql
    assert "ON DELETE CASCADE" in sql


def test_offline_downgrade_drops_every_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", MYSQL_URL)
    config = _alembic_config()
    buffer = io.StringIO()
    config.output_buffer = buffer

    command.downgrade(config, f"{INITIAL_REVISION}:base", sql=True)
    sql = buffer.getvalue()

    for table in EXPECTED_TABLES:
        assert f"DROP TABLE {table}" in sql
    assert "DROP INDEX ix_users_username ON users" in sql
