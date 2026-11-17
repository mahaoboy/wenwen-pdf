"""密码重置：令牌签发与校验（内存存储，一次性消费）。

- 令牌：URL-safe 随机串，SHA-256 哈希存储
- TTL：15 分钟（邮件到达后用户操作窗口）
- 一次性：校验成功后立即消费，防止重放
- 进程重启即失效（MVP 可接受，用户重新申请即可）
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time

TTL_SECONDS = 900  # 15 分钟

_store: dict[str, tuple[str, float]] = {}  # token_hash -> (email, expires_at)
_lock = threading.Lock()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue(email: str) -> str:
    """签发重置令牌。返回原始令牌（明文，仅此一次，用于拼接邮件链接）。"""
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        _store[_hash(token)] = (email, now + TTL_SECONDS)
    return token


def verify(token: str) -> str | None:
    """校验并消费令牌。成功返回 email，失败/过期/已消费返回 None。"""
    with _lock:
        entry = _store.get(_hash(token))
        if entry is None:
            return None
        email, expires = entry
        if expires <= time.time():
            _store.pop(_hash(token), None)
            return None
        _store.pop(_hash(token), None)  # 一次性消费
        return email
