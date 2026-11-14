"""邮箱验证码：注册/验证流程的码签发与校验（内存存储）。

- 6 位数字，10 分钟有效，5 次尝试上限
- 重发冷却 60 秒
- 进程重启即失效（MVP 可接受，重新走一遍注册即可）
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time

TTL_SECONDS = 600
ISSUE_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5

_store: dict[str, tuple[str, float, int]] = {}  # email -> (code_hash, expires, attempts)
_last_issue: dict[str, float] = {}
_lock = threading.Lock()


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def issue(email: str) -> tuple[str, str] | None:
    """签发验证码。冷却期内返回 None。返回 (code, expires_at)。"""
    now = time.time()
    with _lock:
        last = _last_issue.get(email)
        if last is not None and now - last < ISSUE_COOLDOWN_SECONDS:
            return None
        code = f"{secrets.randbelow(1_000_000):06d}"
        _store[email] = (_hash(code), now + TTL_SECONDS, 0)
        _last_issue[email] = now
    return code, now + TTL_SECONDS


def verify(email: str, code: str) -> bool:
    """校验并消费验证码（错误累计 5 次作废）。"""
    with _lock:
        entry = _store.get(email)
        if entry is None:
            return False
        code_hash, expires, attempts = entry
        if expires <= time.time() or attempts >= MAX_ATTEMPTS:
            _store.pop(email, None)
            return False
        if secrets.compare_digest(_hash(code.strip()), code_hash):
            _store.pop(email, None)  # 成功即消费
            return True
        _store[email] = (code_hash, expires, attempts + 1)
        return False


def seconds_until_resend(email: str) -> int:
    now = time.time()
    with _lock:
        last = _last_issue.get(email)
        if last is None:
            return 0
        remain = ISSUE_COOLDOWN_SECONDS - int(now - last)
    return max(0, remain)
