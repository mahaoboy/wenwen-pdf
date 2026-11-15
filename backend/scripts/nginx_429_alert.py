#!/usr/bin/env python3
"""nginx 429 洪峰检测 + 邮件告警（crontab 每分钟调用）。

读取 nginx access log 最近 5 分钟内的 429（限速触发）请求数，
超过阈值即通过 Gmail API 发告警邮件（内置 30 分钟冷却防轰炸）。

crontab: * * * * * root /opt/wenwen/backend/.venv/bin/python /opt/wenwen/backend/scripts/nginx_429_alert.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LOG_FILE = Path("/var/log/nginx/access.log")
STATE_FILE = Path("/tmp/wenwen_429_alert_last")
WINDOW_MINUTES = 5
THRESHOLD = 25
COOLDOWN_SECONDS = 1800


def parse_time(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw, "%d/%b/%Y:%H:%M:%S %z")
    except (ValueError, TypeError):
        return None


def main() -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=WINDOW_MINUTES)

    count = 0
    sample_ip = ""
    if LOG_FILE.exists():
        with LOG_FILE.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 512 * 1024))
            for line in f.read().decode("utf-8", "replace").splitlines():
                parts = line.split()
                if len(parts) < 9 or not parts[-2].startswith("429"):
                    continue
                t = parse_time(parts[3].strip("[")) if len(parts) > 3 else None
                if t and t >= cutoff.replace(tzinfo=t.tzinfo):
                    count += 1
                    sample_ip = sample_ip or parts[0]

    state = Path(str(STATE_FILE))
    if count < THRESHOLD:
        state.unlink(missing_ok=True)
        return 0

    if state.exists():
        age = time.time() - state.stat().st_mtime
        if age < COOLDOWN_SECONDS:
            return 0  # 冷却期内
    state.write_text(str(time.time()))

    from app.core.config import get_settings
    from app.services.alert_mail import send_alert_email

    settings = get_settings()
    to = settings.alert_email or sender_address_fallback()
    body = (
        f"nginx 检测到 429 限速洪峰：\n\n"
        f"最近 {WINDOW_MINUTES} 分钟内触发限速 {count} 次（阈值 {THRESHOLD}）\n"
        f"样本来源 IP：{sample_ip or '未知'}\n"
        f"时间：{now.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
        f"可能是自动化攻击/爬虫，建议评估是否封禁该来源。\n"
        f"本告警 30 分钟冷却。"
    )
    sent = send_alert_email(to, f"⚠️ 文问安全告警：429 限速洪峰（{count} 次/5min）", body)
    print(f"429 洪峰 {count} 次，告警{'已发送' if sent else '失败'}")
    return 0


def sender_address_fallback() -> str:
    try:
        from app.services.gmail_sender import sender_email

        return sender_email(get_settings())
    except Exception:
        return "mahaoboy@gmail.com"


if __name__ == "__main__":
    sys.exit(main())
