"""initial schema: users / rbac / files / chat / stats

Revision ID: 0001_initial_schema
Revises:
Create Date: 2025-01-01 00:00:00.000000

手写初始迁移, 与 app/models 下的 ORM 定义逐列对齐:

    users, roles, permissions, user_roles, role_permissions,
    stored_files, chat_rooms, chat_messages, daily_stats

说明:
* 约束名全部显式给出, 与 app/core/database.py 的 naming_convention 保持一致
  (pk_<table> / ix_<table>_<column> / uq_<table>_<column> / fk_<table>_<column>_<reftable>)。
* 模型里 `unique=True, index=True` 的列 (users.username/email, roles.code,
  stored_files.object_name, chat_rooms.code) 同时建唯一约束 (uq_*) 与普通索引 (ix_*),
  在 MySQL 中唯一约束本身即唯一索引, 两者并存只为约束名显式可读。
* created_at / updated_at 使用 `sa.DateTime(timezone=True)` + `server_default=sa.text('now()')`,
  与 TimestampMixin 一致 (MySQL DATETIME 不存时区, 应用侧统一按 UTC 写入)。
* 计数/容量类字段使用 BigInteger。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=191), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)

    # ------------------------------------------------------------------ roles
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=False)
    op.create_index("ix_roles_created_at", "roles", ["created_at"], unique=False)

    # ------------------------------------------------------------ permissions
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=96), nullable=False),
        sa.Column("name", sa.String(length=96), nullable=False),
        sa.Column("module", sa.String(length=48), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=False)
    op.create_index("ix_permissions_module", "permissions", ["module"], unique=False)
    op.create_index("ix_permissions_created_at", "permissions", ["created_at"], unique=False)

    # -------------------------------------------------------------- user_roles
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_roles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_user_roles_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
    )

    # -------------------------------------------------------- role_permissions
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_role_permissions_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name="fk_role_permissions_permission_id_permissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
    )

    # ----------------------------------------------------------- stored_files
    op.create_table(
        "stored_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("object_name", sa.String(length=512), nullable=False),
        sa.Column("bucket", sa.String(length=96), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("etag", sa.String(length=96), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_stored_files_owner_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stored_files"),
        sa.UniqueConstraint("object_name", name="uq_stored_files_object_name"),
    )
    op.create_index("ix_stored_files_object_name", "stored_files", ["object_name"], unique=False)
    op.create_index("ix_stored_files_category", "stored_files", ["category"], unique=False)
    op.create_index("ix_stored_files_status", "stored_files", ["status"], unique=False)
    op.create_index("ix_stored_files_owner_id", "stored_files", ["owner_id"], unique=False)
    op.create_index("ix_stored_files_created_at", "stored_files", ["created_at"], unique=False)

    # ------------------------------------------------------------- chat_rooms
    op.create_table(
        "chat_rooms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=96), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_rooms"),
        sa.UniqueConstraint("code", name="uq_chat_rooms_code"),
    )
    op.create_index("ix_chat_rooms_code", "chat_rooms", ["code"], unique=False)
    op.create_index("ix_chat_rooms_created_at", "chat_rooms", ["created_at"], unique=False)

    # ---------------------------------------------------------- chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=True),
        sa.Column("sender_name", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["chat_rooms.id"],
            name="fk_chat_messages_room_id_chat_rooms",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name="fk_chat_messages_sender_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
    )
    op.create_index("ix_chat_messages_room_id", "chat_messages", ["room_id"], unique=False)
    op.create_index("ix_chat_messages_kind", "chat_messages", ["kind"], unique=False)
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"], unique=False)
    op.create_index(
        "ix_chat_messages_room_created",
        "chat_messages",
        ["room_id", "created_at"],
        unique=False,
    )

    # ------------------------------------------------------------ daily_stats
    op.create_table(
        "daily_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(length=48), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("dimension", sa.String(length=48), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_stats"),
    )
    op.create_index("ix_daily_stats_stat_date", "daily_stats", ["stat_date"], unique=False)
    op.create_index("ix_daily_stats_metric", "daily_stats", ["metric"], unique=False)
    op.create_index("ix_daily_stats_created_at", "daily_stats", ["created_at"], unique=False)
    op.create_index(
        "ix_daily_stats_date_metric",
        "daily_stats",
        ["stat_date", "metric"],
        unique=False,
    )


def downgrade() -> None:
    # 与 upgrade 完全对称: 先删索引再删表 (MySQL 删表会连带删索引, 显式写出便于跨库回滚)
    op.drop_index("ix_daily_stats_date_metric", table_name="daily_stats")
    op.drop_index("ix_daily_stats_created_at", table_name="daily_stats")
    op.drop_index("ix_daily_stats_metric", table_name="daily_stats")
    op.drop_index("ix_daily_stats_stat_date", table_name="daily_stats")
    op.drop_table("daily_stats")

    op.drop_index("ix_chat_messages_room_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_kind", table_name="chat_messages")
    op.drop_index("ix_chat_messages_room_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_rooms_created_at", table_name="chat_rooms")
    op.drop_index("ix_chat_rooms_code", table_name="chat_rooms")
    op.drop_table("chat_rooms")

    op.drop_index("ix_stored_files_created_at", table_name="stored_files")
    op.drop_index("ix_stored_files_owner_id", table_name="stored_files")
    op.drop_index("ix_stored_files_status", table_name="stored_files")
    op.drop_index("ix_stored_files_category", table_name="stored_files")
    op.drop_index("ix_stored_files_object_name", table_name="stored_files")
    op.drop_table("stored_files")

    op.drop_table("role_permissions")
    op.drop_table("user_roles")

    op.drop_index("ix_permissions_created_at", table_name="permissions")
    op.drop_index("ix_permissions_module", table_name="permissions")
    op.drop_index("ix_permissions_code", table_name="permissions")
    op.drop_table("permissions")

    op.drop_index("ix_roles_created_at", table_name="roles")
    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
