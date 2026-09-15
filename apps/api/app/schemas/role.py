"""角色与权限 Schema。"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ORMModel, TimestampedOut


class PermissionOut(ORMModel):
    id: int
    code: str
    name: str
    module: str
    description: str | None = None


class RoleOut(TimestampedOut):
    id: int
    code: str
    name: str
    description: str | None = None
    is_builtin: bool = False
    permissions: list[str] = Field(default_factory=list)


class RoleCreate(ORMModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_:.-]*$")
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(ORMModel):
    name: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] | None = None


class RoleAssign(ORMModel):
    role_codes: list[str] = Field(default_factory=list)
