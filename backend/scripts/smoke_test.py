"""端到端冒烟测试: 鉴权 + 授权全链路。

用法(在 backend/ 目录下):
    python scripts/smoke_test.py

脚本自己拼一个只挂 user/rbac 两个路由的 FastAPI 应用, 用 SQLite + 内存 KV,
不依赖 MySQL / Redis / 真实邮箱(邮件走控制台兜底通道), 因此可以在任何机器上跑。


覆盖点:
    1. 注册 / 用户名密码登录 / 正确与错误密码的提示一致
    2. 未登录 401、普通用户访问后台 403、管理员放行
    3. 角色 CRUD、权限勾选、用户多角色分配
    4. 退出登录后令牌立即失效
    5. 邮箱验证码登录(兜底通道回显)
    6. 重置密码后旧令牌失效(密码版本机制)
"""

from __future__ import annotations

import os

os.environ.update(
    USE_SQLITE="true",
    REDIS_ENABLED="false",
    MAIL_ENABLED="false",
    MAIL_FALLBACK_CONSOLE="true",
    APP_ENV="development",
    SECRET_KEY="0123456789abcdef0123456789abcdef0123456789abcdef",
    AUTO_CREATE_TABLES="true",
)

import pathlib  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402

# database.py 里 SQLite 的地址是相对路径 "./app_local.db",
# 所以先切到一个临时目录, 既保证每次都从空库开始, 也不会碰到开发机的真实数据库。
BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
WORK_DIR = pathlib.Path(tempfile.mkdtemp(prefix="kaoyan_smoke_"))
os.chdir(WORK_DIR)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import create_all, get_session_factory  # noqa: E402
from app.core.exceptions import register_exception_handlers  # noqa: E402
from app.core.seed import seed_rbac  # noqa: E402
from app.modules.rbac.router import router as rbac_router  # noqa: E402
from app.modules.user.router import router as user_router  # noqa: E402

create_all()
session = get_session_factory()()
print("seed:", seed_rbac(session))
session.close()

app = FastAPI()
register_exception_handlers(app)
app.include_router(user_router)
app.include_router(rbac_router)
client = TestClient(app, raise_server_exceptions=False)

ok, fail = 0, 0


def check(name: str, cond: bool, extra: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail += 1
        print(f"  [FAIL] {name} -> {extra}")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


print("\n=== 1. 注册与密码登录 ===")
r = client.post(
    "/api/user/register",
    json={
        "username": "student1",
        "email": "student1@example.com",
        "password": "abc12345",
    },
)
check("注册成功 201", r.status_code == 201, r.text[:200])
check("返回昵称默认用登录名", r.json().get("username") == "student1", r.text[:200])

weak = client.post(
    "/api/user/register",
    json={"username": "weakuser", "email": "weak@example.com", "password": "12345678"},
)
check("纯数字弱密码被拒", weak.status_code == 400 and "字母" in weak.text, weak.text[:200])

dup = client.post(
    "/api/user/register",
    json={"username": "student1", "email": "other@example.com", "password": "abc12345"},
)
check("用户名重复被拒 409", dup.status_code == 409, dup.text[:200])

r = client.post("/api/user/login", json={"username": "student1", "password": "wrongpass1"})
check("错误密码 401", r.status_code == 401, r.text[:200])
check("错误密码提示不区分账号是否存在", "账号或密码错误" in r.text, r.text[:200])

nobody = client.post("/api/user/login", json={"username": "nobody", "password": "wrongpass1"})
check("不存在账号提示与错误密码一致", "账号或密码错误" in nobody.text, nobody.text[:200])

r = client.post("/api/user/login", json={"username": "student1", "password": "abc12345"})
check("正确密码登录 200", r.status_code == 200, r.text[:200])
student_token = r.json()["access_token"]
check("登录返回角色", r.json()["roles"] == ["考研学生"], r.json().get("roles"))
check("登录返回 7 条权限", len(r.json()["permissions"]) == 7, r.json().get("permissions"))

print("\n=== 2. 登录态与权限边界 ===")
check("未登录访问 /me 返回 401", client.get("/api/user/me").status_code == 401)
check(
    "伪造令牌返回 401",
    client.get("/api/user/me", headers=auth("abc.def.ghi")).status_code == 401,
)
r = client.get("/api/user/me", headers=auth(student_token))
check("登录后 /me 200", r.status_code == 200, r.text[:200])
check("资料里带权限", len(r.json()["permissions"]) == 7, r.json().get("permissions"))

r = client.put(
    "/api/user/me",
    headers=auth(student_token),
    json={
        "nickname": "小明",
        "undergraduate_major": "软件工程",
        "major": "计算机科学与技术",
        "target_area": "四川",
        "prep_stage": "强化",
        "target_score": 380,
    },
)
check("修改资料成功", r.status_code == 200, r.text[:200])
check("昵称已写入 user_account", r.json()["nickname"] == "小明", r.json())
check("本科专业已写入", r.json()["undergraduate_major"] == "软件工程", r.json())
check("报考专业已写入", r.json()["major"] == "计算机科学与技术", r.json())
check("目标地区已写入", r.json()["target_area"] == "四川", r.json())
check("目标分数已写入", r.json()["target_score"] == 380, r.json())

check(
    "考生访问角色管理 403",
    client.get("/api/admin/roles", headers=auth(student_token)).status_code == 403,
)
check(
    "考生访问用户管理 403",
    client.get("/api/admin/users", headers=auth(student_token)).status_code == 403,
)

print("\n=== 3. 管理员与角色管理 ===")
r = client.post("/api/user/login", json={"username": "admin", "password": "Admin@123456"})
check("管理员登录 200", r.status_code == 200, r.text[:200])
admin_token = r.json()["access_token"]
check("管理员拥有全部 16 条权限", len(r.json()["permissions"]) == 16, len(r.json()["permissions"]))

r = client.get("/api/admin/roles", headers=auth(admin_token))
check("角色列表 200", r.status_code == 200, r.text[:200])
check("初始 2 个角色", len(r.json()) == 2, r.text[:300])
check("内置角色标记正确", {x["role_name"]: x["built_in"] for x in r.json()} == {"考研学生": True, "系统管理员": True}, r.text[:300])

r = client.get("/api/admin/permissions", headers=auth(admin_token))
check("权限分组 7 组", len(r.json()) == 7, [g["module_name"] for g in r.json()])
check("权限总数 16", sum(len(g["permissions"]) for g in r.json()) == 16)

r = client.post("/api/admin/roles", headers=auth(admin_token), json={"role_name": "助教", "role_desc": "帮忙看计划"})
check("新增角色 200", r.status_code == 200, r.text[:300])
role_id = r.json()["role_id"]

r = client.post("/api/admin/roles", headers=auth(admin_token), json={"role_name": "助教"})
check("角色重名被拒 409", r.status_code == 409, r.text[:200])

r = client.put(
    f"/api/admin/roles/{role_id}",
    headers=auth(admin_token),
    json={"role_name": "助教老师", "role_desc": "协助管理学习计划"},
)
check("修改角色 200", r.status_code == 200 and r.json()["role_name"] == "助教老师", r.text[:300])

# 给助教角色勾选 role:manage + user:manage
perms = client.get("/api/admin/permissions", headers=auth(admin_token)).json()
all_perms = [p for g in perms for p in g["permissions"]]
target_ids = [p["perm_id"] for p in all_perms if p["perm_key"] in ("role:manage", "user:manage")]
r = client.put(
    f"/api/admin/roles/{role_id}/permissions",
    headers=auth(admin_token),
    json={"perm_ids": target_ids},
)
check("保存角色权限 200", r.status_code == 200 and r.json() == sorted(target_ids), r.text[:300])
check(
    "回读角色权限一致",
    client.get(f"/api/admin/roles/{role_id}/permissions", headers=auth(admin_token)).json() == sorted(target_ids),
)

r = client.get("/api/admin/users", headers=auth(admin_token))
check("用户列表 200", r.status_code == 200, r.text[:300])
users = r.json()["items"]
student_id = next(u["user_id"] for u in users if u["login_name"] == "student1")

r = client.put(
    f"/api/admin/users/{student_id}/roles",
    headers=auth(admin_token),
    json={"role_ids": [1, role_id]},
)
check(
    "用户多角色分配成功",
    r.status_code == 200 and {x["role_id"] for x in r.json()} == {1, role_id},
    r.text[:300],
)

r = client.get("/api/admin/roles", headers=auth(student_token))
check("考生获得 role:manage 后可访问角色管理", r.status_code == 200, r.text[:200])

r = client.delete(f"/api/admin/roles/{role_id}", headers=auth(admin_token))
check("内置/在用角色不能删: 该角色仍有用户 -> 409", r.status_code == 409, r.text[:200])

# 解除分配后再删
client.put(f"/api/admin/users/{student_id}/roles", headers=auth(admin_token), json={"role_ids": [1]})
r = client.delete(f"/api/admin/roles/{role_id}", headers=auth(admin_token))
check("解除分配后可删除角色", r.status_code == 200, r.text[:200])

r = client.delete("/api/admin/roles/2", headers=auth(admin_token))
check("内置系统管理员角色不可删", r.status_code == 400, r.text[:200])

print("\n=== 4. 账号启停 ===")
r = client.patch(f"/api/admin/users/{student_id}/status", headers=auth(admin_token), json={"account_status": 0})
check("禁用账号 200", r.status_code == 200 and r.json()["account_status"] == 0, r.text[:300])
check("被禁用后旧令牌立即 403", client.get("/api/user/me", headers=auth(student_token)).status_code == 403)
r = client.patch(f"/api/admin/users/{student_id}/status", headers=auth(admin_token), json={"account_status": 1})
check("重新启用 200", r.status_code == 200, r.text[:200])
check("启用后令牌恢复可用", client.get("/api/user/me", headers=auth(student_token)).status_code == 200)

print("\n=== 5. 审计日志 ===")
r = client.get("/api/admin/audit-logs", headers=auth(admin_token), params={"size": 100})
check("审计日志有记录", r.status_code == 200 and r.json()["total"] >= 8, r.text[:200])
actions = {item["action"] for item in r.json()["items"]}
check("包含角色授权动作", "role.permission.update" in actions, actions)
check("包含登录失败动作", "login.failure" in actions, actions)
r = client.get("/api/admin/audit-logs", headers=auth(student_token))
check("考生看审计日志 403", r.status_code == 403, r.status_code)

print("\n=== 6. 退出登录与令牌吊销 ===")
r = client.post("/api/user/logout", headers=auth(student_token))
check("退出登录 200", r.status_code == 200, r.text[:200])
check("退出后原令牌 401", client.get("/api/user/me", headers=auth(student_token)).status_code == 401)

print("\n=== 7. 邮箱验证码登录 ===")
r = client.post("/api/user/email-code", json={"email": "student1@example.com", "purpose": "login"})
check("发送验证码 200", r.status_code == 200, r.text[:300])
check("兜底通道回显验证码", r.json().get("channel") == "console" and r.json().get("dev_code"), r.text[:300])
code = r.json()["dev_code"]

cooldown = client.post("/api/user/email-code", json={"email": "student1@example.com", "purpose": "login"})
check("60 秒内重复发送被拒", cooldown.status_code == 400, cooldown.text[:200])

r = client.post("/api/user/login/email", json={"email": "student1@example.com", "code": "000000"})
check("错误验证码被拒", r.status_code == 400, r.text[:200])

r = client.post("/api/user/login/email", json={"email": "student1@example.com", "code": code})
check("验证码登录 200", r.status_code == 200, r.text[:300])
email_token = r.json()["access_token"]

r = client.post("/api/user/login/email", json={"email": "student1@example.com", "code": code})
check("验证码一次性(重放被拒)", r.status_code == 400, r.text[:200])

print("\n=== 8. 重置密码后旧令牌失效 ===")
r = client.post("/api/user/email-code", json={"email": "student1@example.com", "purpose": "reset"})
reset_code = r.json()["dev_code"]
r = client.post(
    "/api/user/password/reset",
    json={"email": "student1@example.com", "code": reset_code, "new_password": "newpass123"},
)
check("重置密码 200", r.status_code == 200, r.text[:300])
check("旧令牌立即失效", client.get("/api/user/me", headers=auth(email_token)).status_code == 401)
r = client.post("/api/user/login", json={"username": "student1", "password": "newpass123"})
check("新密码可登录", r.status_code == 200, r.text[:200])
new_token = r.json()["access_token"]

print("\n=== 9. 登录失败锁定 ===")
for _ in range(4):
    client.post("/api/user/login", json={"username": "student1", "password": "badpass1"})
r = client.post("/api/user/login", json={"username": "student1", "password": "badpass1"})
check("第 5 次失败返回锁定提示", r.status_code == 400 and "次数过多" in r.text, r.text[:200])
r = client.post("/api/user/login", json={"username": "student1", "password": "newpass123"})
check("锁定期间正确密码也拒绝", r.status_code == 400 and "次数过多" in r.text, r.text[:200])
r = client.post("/api/user/login", json={"username": "student1@example.com", "password": "newpass123"})
check("换邮箱标识登录同样被锁定", r.status_code == 400 and "次数过多" in r.text, r.text[:200])

print(f"\n结果: {ok} 通过 / {fail} 失败")
raise SystemExit(0 if fail == 0 else 1)
