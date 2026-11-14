"""账单路由：套餐查询 / 买断 / 订阅支付下单。阶段 5 接入微信支付+支付宝沙箱。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db import Document, QuotaUsage, User
from app.db.session import get_db
from app.schemas import QuotaOut

router = APIRouter(prefix="/billing", tags=["billing"])

PLAN_LIMITS = {
    "free": ("free_doc_limit", "free_question_limit"),
    "buyout": ("buyout_doc_limit", "buyout_question_limit"),
    "monthly": ("sub_monthly_doc_limit", "sub_monthly_question_limit"),
    "yearly": ("sub_monthly_doc_limit", "sub_monthly_question_limit"),
}


@router.get("/quota", response_model=QuotaOut)
def get_quota(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuotaOut:
    settings = get_settings()
    doc_key, q_key = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
    doc_used = db.query(Document).filter(Document.user_id == user.id).count()
    usage = db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).first()
    return QuotaOut(
        plan=user.plan,
        doc_used=doc_used,
        doc_limit=getattr(settings, doc_key),
        question_used=usage.question_count if usage else 0,
        question_limit=getattr(settings, q_key),
    )


@router.post("/orders")
def create_order(
    plan: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),  # noqa: ARG001 保持签名一致
) -> dict:
    """创建买断/订阅订单。TODO(阶段5): 接入微信支付 Native 下单 + 支付宝电脑网站支付，回调后升级 user.plan。"""
    if plan not in {"buyout", "monthly", "yearly"}:
        return {"error": "无效套餐，仅支持 buyout / monthly / yearly"}
    # TODO(阶段5): 生成订单记录 + 拉起支付二维码
    return {"order_id": None, "status": "not_implemented", "plan": plan}
