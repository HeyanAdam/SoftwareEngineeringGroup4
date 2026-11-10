"""图形验证码: 密码登录的防机器人闸门。

设计(移植 rjgc 的图符验证码思路, 见 rjgc/明文密文说明.md):
    * SVG 文本验证码: 4 位随机字符(去除 0/O/1/I 等易混淆字符),
      随机旋转 / 位置 / 颜色 + 噪声线与噪点, 纯字符串拼接, 无第三方绘图依赖;
    * 答案统一小写存入 KV, 一次性使用(无论对错立即作废), 默认 300 秒过期;
    * 触发时机: 密码登录连续失败 CAPTCHA_AFTER_FAILURES 次(默认 2)后强制要求,
      失败计数沿用登录锁定的三维度键(输入标识 / 用户名 / user_id), 换标识无法绕过;
    * 校验不区分大小写, 比对用 hmac.compare_digest。
"""

from __future__ import annotations

import hmac
import random
import secrets
import uuid

from app.core.config import settings
from app.core.store import get_store

CAPTCHA_KEY = "captcha:{cid}"
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_COLORS = ("#1e5eff", "#d64541", "#2c9e5f", "#b8860b", "#6a3ec9")


def _render_svg(code: str) -> str:
    rng = random.Random()
    parts: list[str] = []
    for _ in range(3):  # 噪声线
        parts.append(
            f'<line x1="{rng.randint(0, 20)}" y1="{rng.randint(0, 42)}" '
            f'x2="{rng.randint(100, 132)}" y2="{rng.randint(0, 42)}" '
            f'stroke="{rng.choice(_COLORS)}" stroke-width="1" opacity="0.5"/>'
        )
    for _ in range(24):  # 噪点
        parts.append(
            f'<circle cx="{rng.randint(0, 132)}" cy="{rng.randint(0, 42)}" r="1" '
            f'fill="{rng.choice(_COLORS)}" opacity="0.4"/>'
        )
    for i, ch in enumerate(code):
        x = 16 + i * 27 + rng.randint(-4, 4)
        y = 28 + rng.randint(-4, 4)
        rotate = rng.randint(-28, 28)
        parts.append(
            f'<text x="{x}" y="{y}" transform="rotate({rotate} {x} {y})" '
            f'font-size="{rng.randint(20, 26)}" font-weight="700" '
            f'fill="{rng.choice(_COLORS)}" font-family="Verdana, sans-serif">{ch}</text>'
        )
    body = "".join(parts)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="132" height="42" '
        f'viewBox="0 0 132 42">{body}</svg>'
    )


def create_captcha() -> dict:
    """生成一组验证码: {"captcha_id", "svg", "expires_in"}。svg 直接给前端 v-html 渲染。"""
    code = "".join(secrets.choice(_ALPHABET) for _ in range(4))
    captcha_id = uuid.uuid4().hex
    get_store().set(
        CAPTCHA_KEY.format(cid=captcha_id), code.lower(), ttl=settings.CAPTCHA_TTL_SECONDS
    )
    return {
        "captcha_id": captcha_id,
        "svg": _render_svg(code),
        "expires_in": settings.CAPTCHA_TTL_SECONDS,
    }


def verify_captcha(captcha_id: str | None, code: str | None) -> bool:
    """校验验证码。一次性: 无论对错都立即作废, 防重放。"""
    if not captcha_id or not code:
        return False
    key = CAPTCHA_KEY.format(cid=captcha_id.strip())
    store = get_store()
    expected = store.get(key)
    store.delete(key)
    if expected is None:
        return False
    return hmac.compare_digest(expected, code.strip().lower())
