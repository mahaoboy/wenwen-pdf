"""邮件发送：Gmail API（OAuth 复用）与 SMTP 双通道，按配置自动选择。

未配置任何通道时 send 返回 False——调用方进入开发模式
（验证码直接展示给用户，明确标注），注册流程不受阻。
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings
from app.services.gmail_sender import gmail_api_configured, send_via_gmail

logger = logging.getLogger(__name__)


def email_configured() -> bool:
    """是否已配置任一可用邮件通道。"""
    s = get_settings()
    if s.email_transport == "gmail_api":
        return gmail_api_configured(s)
    return bool(s.smtp_host and s.smtp_user and s.smtp_pass)


def send_verification_email(to: str, code: str) -> bool:
    s = get_settings()
    if s.email_transport == "gmail_api" and gmail_api_configured(s):
        try:
            sent = send_via_gmail(s, to, code)
            if sent:
                logger.info("验证码邮件已发送（Gmail API）to=%s", to)
            return sent
        except Exception:
            logger.exception("Gmail API 发送失败 to=%s", to)
            return False

    if not (s.smtp_host and s.smtp_user and s.smtp_pass):
        logger.info("SMTP 未配置，跳过发信（开发模式）to=%s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【文问】邮箱验证码 {code}（10 分钟内有效）"
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;
                border: 1px solid #eee; border-radius: 12px;">
      <h2 style="color: #c2402a;">文问 WenWen · 邮箱验证</h2>
      <p>你的验证码：</p>
      <p style="font-size: 28px; font-weight: bold; letter-spacing: 6px; color: #1c1e21;">{code}</p>
      <p style="color: #888; font-size: 13px;">10 分钟内有效。如非本人操作，请忽略本邮件。</p>
    </div>
    """
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if s.smtp_ssl:
            with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20) as server:
                server.login(s.smtp_user, s.smtp_pass)
                server.sendmail(s.smtp_from or s.smtp_user, [to], msg.as_string())
        else:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
                server.starttls()
                server.login(s.smtp_user, s.smtp_pass)
                server.sendmail(s.smtp_from or s.smtp_user, [to], msg.as_string())
        logger.info("验证码邮件已发送 to=%s", to)
        return True
    except Exception:
        logger.exception("验证码邮件发送失败 to=%s", to)
        return False
