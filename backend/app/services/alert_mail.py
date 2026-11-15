"""通用告警邮件：安全告警等系统级通知，双通道（gmail_api / smtp）。"""
from __future__ import annotations

import base64
import json
import logging
import smtplib
import urllib.request
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings
from app.services.gmail_sender import gmail_api_configured, load_access_token, sender_email

logger = logging.getLogger(__name__)


def send_alert_email(to: str, subject: str, body: str) -> bool:
    """发送纯文本告警邮件。优先 Gmail API，回落 SMTP。失败返回 False。"""
    s = get_settings()
    if s.email_transport == "gmail_api" and gmail_api_configured(s):
        try:
            access = load_access_token(s)
            msg = EmailMessage()
            msg["To"] = to
            msg["From"] = sender_email(s)
            msg["Subject"] = subject
            msg.set_content(body)
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            req = urllib.request.Request(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                data=json.dumps({"raw": raw}).encode(),
                headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.load(resp)
            return bool(payload.get("id"))
        except Exception:
            logger.exception("告警邮件发送失败（Gmail API）to=%s", to)
            return False

    if not (s.smtp_host and s.smtp_user and s.smtp_pass):
        logger.warning("告警邮件未发送：无可用邮件通道 to=%s", to)
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = s.smtp_from or s.smtp_user
        msg["To"] = to
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if s.smtp_ssl:
            with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20) as server:
                server.login(s.smtp_user, s.smtp_pass)
                server.sendmail(s.smtp_from or s.smtp_user, [to], msg.as_string())
        else:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
                server.starttls()
                server.login(s.smtp_user, s.smtp_pass)
                server.sendmail(s.smtp_from or s.smtp_user, [to], msg.as_string())
        return True
    except Exception:
        logger.exception("告警邮件发送失败（SMTP）to=%s", to)
        return False
