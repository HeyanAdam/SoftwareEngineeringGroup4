"""授权(后台管理)模块请求/响应模型。

对应禅道 L3 的四类操作:
    角色增删改查 / 权限清单(按模块分组) / 角色权限勾选 / 用户多角色分配 + 审计日志。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RoleCreateRequest(BaseModel):
    role_name: str = Field(..., min_length=2, max_length=30, description="角色名称")
    role_desc: str | None = Field(default=None, max_length=200, description="角色描述")

    @field_validator("role_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("角色名称不能为空")
        return value

class RoleUpdateRequest(BaseModel):
    role_name: str | None = Field(default=None, min_length=2, max_length=30)
    role_desc: str | None = Field(default=None, max_length=200)

    @field_validator("role_name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("角色名称不能为空")
        return value

class RoleOut(BaseModel):
    role_id: int
    role_name: str
    role_desc: str | None = None
    user_count: int = 0
    permission_ids: list[int] = Field(default_factory=list)
    built_in: bool = Field(default=False, description="内置角色(考研学生/系统管理员)不允许删除")

class PermissionOut(BaseModel):
    perm_id: int
    perm_key: str
    perm_name: str
    module_name: str

class PermissionGroupOut(BaseModel):
    """按 module_name 分组, 对应禅道权限配置页的分组勾选。"""

    module_name: str
    permissions: list[PermissionOut]

class RolePermissionUpdateRequest(BaseModel):
    perm_ids: list[int] = Field(default_factory=list, description="该角色拥有的权限编号全集")

class UserRoleUpdateRequest(BaseModel):
    role_ids: list[int] = Field(default_factory=list, description="该用户拥有的角色编号全集")

class AccountStatusUpdateRequest(BaseModel):
    account_status: int = Field(..., ge=0, le=1, description="0 禁用, 1 启用")

class RoleBrief(BaseModel):
    role_id: int
    role_name: str

class AdminUserOut(BaseModel):
    user_id: int
    login_name: str
    email: str
    account_status: int
    create_time: datetime
    roles: list[RoleBrief] = Field(default_factory=list)


class AuditLogOut(BaseModel):
    """一条审计日志(直接对应 sys_audit_log 的列)。"""

    id: int
    user_id: int | None = None
    login_name: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    detail: dict[str, Any] | None = None
    ip: str | None = None
    success: bool
    create_time: datetime


class AuditLogPage(BaseModel):
    """审计日志分页结果。"""

    total: int
    items: list[AuditLogOut]
