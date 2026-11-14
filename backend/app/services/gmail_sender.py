"""Gmail API 发信：复用本地已授权的 OAuth 凭据（stdlib-only，零新依赖）。

凭据形态与 memalyze 项目一致：client_secret.json + token.json（含 refresh_token）。
access_token 过期前 2 分钟自动用 refresh_token 续期，并回写 token 文件（0600）。
"""
from __future__ import annotations

import base64
import json
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from app.core.config import Settings

TOKEN_URI = "https://oauth2.googleapis.com/token"
API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"
ACCESS_TOKEN_SAFETY_MARGIN = 120  # 过期前 2 分钟视为过期

_sender_email_cache: tuple[float, str] | None = None


def _load_client(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    client = data.get("installed") or data.get("web")
    if not client or not client.get("client_id") or not client.get("client_secret"):
        raise RuntimeError(f"无效的 OAuth client 文件：{path}")
    return client


def _write_token(path: str, data: dict) -> None:
    target = Path(path)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)


def load_access_token(settings: Settings) -> str:
    token = json.loads(Path(settings.gmail_token_path).read_text(encoding="utf-8"))
    obtained = float(token.get("obtained_at", 0))
    expires = int(token.get("expires_in", 0))
    if token.get("access_token") and time.time() < obtained + expires - ACCESS_TOKEN_SAFETY_MARGIN:
        return token["access_token"]

    if not token.get("refresh_token"):
        raise RuntimeError("token.json 缺少 refresh_token，请重新走一遍 OAuth 授权")

    client = _load_client(settings.gmail_client_secret_path)
    fields = {
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token",
    }
    uri = token.get("token_uri") or TOKEN_URI
    req = urllib.request.Request(
        uri,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)
    if "access_token" not in payload:
        raise RuntimeError(f"refresh 失败：{payload.get('error', 'unknown')}")

    token.update(
        access_token=payload["access_token"],
        expires_in=int(payload.get("expires_in", 3600)),
        obtained_at=time.time(),
    )
    _write_token(settings.gmail_token_path, token)
    return token["access_token"]


def sender_email(settings: Settings) -> str:
    """发件人地址：优先配置，否则从 Gmail profile 读取（缓存 1 小时）。"""
    global _sender_email_cache
    if settings.gmail_from:
        return settings.gmail_from
    if _sender_email_cache and time.time() - _sender_email_cache[0] < 3600:
        return _sender_email_cache[1]
    token = load_access_token(settings)
    req = urllib.request.Request(
        f"{API_ROOT}/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        email = json.load(resp).get("emailAddress", "")
    _sender_email_cache = (time.time(), email)
    return email


def gmail_api_configured(settings: Settings) -> bool:
    return bool(settings.gmail_client_secret_path and settings.gmail_token_path)


def send_via_gmail(settings: Settings, to: str, code: str) -> bool:
    access = load_access_token(settings)
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = sender_email(settings)
    msg["Subject"] = f"【文问】邮箱验证码 {code}（10 分钟内有效）"
    msg.set_content(
        f"你的验证码：{code}\n\n10 分钟内有效。如非本人操作，请忽略本邮件。\n—— 文问 WenWen",
    )

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    req = urllib.request.Request(
        f"{API_ROOT}/messages/send",
        data=json.dumps({"raw": raw}).encode(),
        headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)
    return bool(payload.get("id"))
