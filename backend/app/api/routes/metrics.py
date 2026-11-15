"""监控路由：访问量打点（免鉴权）+ 管理统计（密钥保护）。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.services.metrics import admin_stats, client_ip, record

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


@router.post("/metrics/visit")
def visit(request: Request) -> dict:
    """访问量打点（前端页面加载时调用）。"""
    record("visit", ip=client_ip(request))
    return {"ok": True}


@router.get("/admin/stats")
def admin_panel_stats(request: Request, x_admin_key: str = Header(default="")) -> dict:
    """管理统计：需要 X-Admin-Key 匹配 settings.admin_key（未配置即禁用）。"""
    settings = get_settings()
    if not settings.admin_key:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "管理接口未启用")
    if x_admin_key != settings.admin_key:
        logger.warning("管理统计密钥错误 ip=%s", client_ip(request))
        raise HTTPException(status.HTTP_403_FORBIDDEN, "密钥错误")
    return admin_stats()
