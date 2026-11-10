"""邮箱验证码发送通道。

方案 A + E(用户已确认):
    A. QQ 邮箱 SMTP(SSL 465, 授权码认证) —— 真实发信, 个人邮箱免费
    E. 控制台回显兜底 —— SMTP 没配置或发送失败时, 把验证码打到日志并随接口返回

安全约束:
    * MAIL_ENABLED=0 或未配置账号密码 -> 走兜底;
    * 生产环境(APP_ENV=production)**强制禁止回显**, 否则邮箱验证码等于形同虚设;
    * 发信失败且不允许回显 -> 返回 503, 前端提示稍后重试。

只用标准库 smtplib + ssl, 不引入任何第三方发信 SDK, 也不产生费用。
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Literal

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger("kaoyan.mailer")

CodePurpose = Literal["login", "reset", "register"]

PURPOSE_TEXT: dict[str, str] = {
    "login": "登录",
    "reset": "重置密码",
    "register": "注册",
}


def _code_mail_html(code: str, minutes: int, purpose_cn: str) -> str:
    """验证码邮件 HTML 模板(移植自 rjgc/lib/mailer.js 的 codeMailHtml)。"""
    return f"""\
  <div style="max-width:520px;margin:0 auto;font-family:'Microsoft YaHei',sans-serif;border:1px solid #e3e8f2;border-radius:12px;overflow:hidden">
    <div style="background:linear-gradient(90deg,#0e3ea8,#1e5eff);color:#fff;padding:18px 24px;font-size:17px;font-weight:700">
      {settings.APP_NAME}
    </div>
    <div style="padding:26px 24px;color:#1c2333;font-size:14px;line-height:1.8">
      <p>您好！你正在进行<b>{purpose_cn}</b>，验证码为：</p>
      <p style="text-align:center;margin:18px 0">
        <span style="display:inline-block;background:#f0f5ff;border:1px dashed #1e5eff;border-radius:10px;
                     padding:12px 26px;font-size:30px;letter-spacing:8px;font-weight:800;color:#1249d6">{code}</span>
      </p>
      <p style="color:#7a839e;font-size:13px">验证码 <b>{minutes} 分钟</b>内有效、一次性使用，请勿泄露给他人。若非本人操作，请忽略本邮件。</p>
    </div>
    <div style="background:#f7f9fe;color:#98a2bb;font-size:12px;text-align:center;padding:12px">
      本邮件由系统自动发送，请勿回复 · {settings.APP_NAME}
    </div>
  </div>"""


def _build_message(to_email: str, code: str, purpose: str, ttl_seconds: int) -> EmailMessage:
    purpose_cn = PURPOSE_TEXT.get(purpose, purpose)
    minutes = max(1, ttl_seconds // 60)
    message = EmailMessage()
    message["From"] = formataddr((settings.MAIL_FROM_NAME, settings.MAIL_USERNAME))
    message["To"] = to_email
    message["Subject"] = f"【{settings.APP_NAME}】{purpose_cn}验证码"
    # 纯文本兜底(不支持 HTML 的客户端), HTML 为首选展示
    message.set_content(
        f"你好:\n\n"
        f"你正在进行{purpose_cn}操作, 验证码是: {code}\n"
        f"验证码 {minutes} 分钟内有效, 只能使用一次, 请勿转发给他人。\n\n"
        f"如果这不是你本人的操作, 请忽略本邮件。\n\n"
        f"{settings.APP_NAME}"
    )
    message.add_alternative(_code_mail_html(code, minutes, purpose_cn), subtype="html")
    return message


def _send_via_smtp(to_email: str, code: str, purpose: str, ttl_seconds: int) -> None:
    message = _build_message(to_email, code, purpose, ttl_seconds)
    context = ssl.create_default_context()
    if settings.MAIL_USE_SSL:
        with smtplib.SMTP_SSL(
            settings.MAIL_HOST, settings.MAIL_PORT, timeout=10, context=context
        ) as smtp:
            smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.MAIL_HOST, settings.MAIL_PORT, timeout=10) as smtp:
            smtp.starttls(context=context)
            smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            smtp.send_message(message)


def send_verification_code(
    to_email: str, code: str, purpose: CodePurpose, ttl_seconds: int
) -> dict[str, Any]:
    """发送验证码, 返回 {"channel": "smtp"|"console", "dev_code": str|None}。

    只有走进兜底通道时才会把验证码回显给调用方, 用于本地联调和答辩演示。
    """
    if settings.MAIL_ENABLED and settings.mail_configured:
        try:
            _send_via_smtp(to_email, code, purpose, ttl_seconds)
            logger.info("验证码已通过 SMTP 发送至 %s", to_email)
            return {"channel": "smtp", "dev_code": None}
        except Exception as exc:  # noqa: BLE001  SMTP 失败原因很多(授权码/端口/网络)
            logger.error("SMTP 发送失败: %s", exc)
            if not settings.mail_fallback_allowed:
                raise AppError(
                    "邮件发送失败, 请稍后重试或联系管理员",
                    code=50300,
                    status_code=503,
                )
            logger.warning("已降级为控制台回显, 收件人=%s", to_email)
            logger.warning("[DEV] 邮箱验证码 purpose=%s code=%s", purpose, code)
            return {"channel": "console", "dev_code": code}

    if not settings.mail_fallback_allowed:
        # 生产环境未配置邮件通道: 明确报错, 绝不把验证码返回前端
        raise AppError(
            "服务器未配置邮件通道, 暂时无法发送验证码",
            code=50300,
            status_code=503,
        )

    logger.warning("[DEV] 邮件通道未启用, 验证码只回显到控制台")
    logger.warning("[DEV] 收件人=%s purpose=%s code=%s", to_email, purpose, code)
    return {"channel": "console", "dev_code": code}
