"""轻量监控：事件采集、聚合统计、攻击检测与邮件告警。

设计约束：1 核 / 961MB 云服务器——不引入 Langfuse/Postgres 等重服务，
直接写 SQLite + 数据库滑窗计数，告警复用 Gmail 发信通道（带冷却防轰炸）。
"""
from __future__ import annotations

import json
import logging
import threading
import time

from fastapi import Request
from sqlalchemy import func, text

from app.core.config import get_settings
from app.db import MetricsEvent, User
from app.db.session import SessionLocal
from app.services.email_sender import email_configured

logger = logging.getLogger(__name__)

# 攻击检测规则：事件类型 -> (窗口内阈值, 窗口秒数)
ATTACK_RULES = {
    "attack_login_fail": (10, 600),
    "attack_captcha_fail": (15, 600),
    "attack_register_burst": (5, 3600),
}
ALERT_COOLDOWN_SECONDS = 1800  # 同一 (类型, IP) 告警冷却 30 分钟，防邮件轰炸

_alert_sent: dict[tuple[str, str], float] = {}
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """取真实客户端 IP（nginx 已写入 X-Real-IP）。"""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "")


def record(event_type: str, ip: str = "", user_id: int | None = None, meta: dict | None = None) -> None:
    """记录事件（fire-safe：监控绝不影响主业务）。"""
    try:
        db = SessionLocal()
        try:
            db.add(
                MetricsEvent(
                    event_type=event_type,
                    ip=ip or "",
                    user_id=user_id,
                    meta=json.dumps(meta or {}, ensure_ascii=False),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("监控事件写入失败 type=%s", event_type)


def record_attack(event_type: str, ip: str, meta: dict | None = None) -> None:
    """记录攻击事件；达到阈值时发告警邮件（带冷却）。"""
    record(event_type, ip=ip, meta=meta)
    rule = ATTACK_RULES.get(event_type)
    if rule is None:
        return
    threshold, window = rule
    now = time.time()
    count = 0
    try:
        db = SessionLocal()
        try:
            cutoff_row = db.execute(
                text("SELECT datetime('now', :sec)"), {"sec": f"-{window} seconds"}
            ).scalar_one()
            count = (
                db.query(MetricsEvent)
                .filter(
                    MetricsEvent.event_type == event_type,
                    MetricsEvent.ip == ip,
                    MetricsEvent.ts >= cutoff_row,
                )
                .count()
            )
        finally:
            db.close()
    except Exception:
        logger.exception("攻击计数查询失败")
        return

    if count < threshold:
        return
    key = (event_type, ip)
    with _lock:
        last = _alert_sent.get(key, 0)
        if now - last < ALERT_COOLDOWN_SECONDS:
            return
        _alert_sent[key] = now
    _send_attack_email(event_type, ip, count, window)


def _send_attack_email(event_type: str, ip: str, count: int, window: int) -> None:
    settings = get_settings()
    if not email_configured():
        logger.warning("攻击告警（邮件通道未配置，仅记录）：%s from %s x%d", event_type, ip, count)
        return
    to = settings.alert_email or sender_address_fallback()
    subject = f"⚠️ 文问安全告警：{event_type}（{ip}）"
    body = (
        f"检测到可疑行为：\n\n"
        f"类型：{event_type}\nIP：{ip}\n"
        f"{window // 60} 分钟窗口内触发 {count} 次（阈值 {ATTACK_RULES[event_type][0]} 次）\n\n"
        f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"建议：如非内部测试，考虑对该 IP 临时封禁（ufw insert 1 deny <ip>）。\n"
        f"本告警 30 分钟内不会重复发送。"
    )
    try:
        from app.services.alert_mail import send_alert_email

        send_alert_email(to, subject, body)
        logger.warning("攻击告警已邮件通知：%s ip=%s x%d", event_type, ip, count)
    except Exception:
        logger.exception("攻击告警邮件发送失败")


def sender_address_fallback() -> str:
    """告警收件人未配置时，回落到 Gmail 发件账号（自发自收）。"""
    try:
        from app.services.gmail_sender import sender_email

        return sender_email(get_settings())
    except Exception:
        return ""


def admin_stats() -> dict:
    """管理面板聚合统计。"""
    db = SessionLocal()
    try:
        users_total = db.query(func.count()).select_from(User).scalar()
        users_verified = (
            db.query(func.count()).select_from(User).filter(User.email_verified.is_(True)).scalar()
        )
        docs_total = db.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        questions_total = db.execute(
            text("SELECT COUNT(*) FROM messages WHERE role='user'")
        ).scalar()
        token_row = db.execute(
            text(
                "SELECT COALESCE(SUM(CAST(JSON_EXTRACT(meta,'$.prompt_tokens') AS INTEGER)),0),"
                " COALESCE(SUM(CAST(JSON_EXTRACT(meta,'$.completion_tokens') AS INTEGER)),0) "
                "FROM metrics_events WHERE event_type='llm_tokens'"
            )
        ).one()
        visits_24h = db.execute(
            text(
                "SELECT COUNT(DISTINCT ip) FROM metrics_events "
                "WHERE event_type='visit' AND ts >= datetime('now','-1 day')"
            )
        ).scalar()
        chats_24h = db.execute(
            text(
                "SELECT COUNT(*) FROM metrics_events "
                "WHERE event_type='chat' AND ts >= datetime('now','-1 day')"
            )
        ).scalar()
        registers_24h = db.execute(
            text(
                "SELECT COUNT(*) FROM metrics_events "
                "WHERE event_type='register' AND ts >= datetime('now','-1 day')"
            )
        ).scalar()
        recent_attacks = (
            db.query(MetricsEvent)
            .filter(MetricsEvent.event_type.like("attack_%"))
            .order_by(MetricsEvent.ts.desc())
            .limit(20)
            .all()
        )
        return {
            "users_total": users_total,
            "users_verified": users_verified,
            "docs_total": docs_total,
            "questions_total": questions_total,
            "tokens_prompt": token_row[0],
            "tokens_completion": token_row[1],
            "visits_24h": visits_24h,
            "chats_24h": chats_24h,
            "registers_24h": registers_24h,
            "recent_attacks": [
                {"ts": str(e.ts), "type": e.event_type, "ip": e.ip, "meta": e.meta}
                for e in recent_attacks
            ],
        }
    finally:
        db.close()
