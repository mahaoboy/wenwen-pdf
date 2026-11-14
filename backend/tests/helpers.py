"""测试助手：统一处理图片验证码与邮箱验证流程。

图片验证码答案从服务端内存存储读取（仅测试可用）；
SMTP 未配置时注册响应含 dev_code（开发模式），用于完成邮箱验证。
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.services.captcha import _store as captcha_store


def solve_captcha(client: TestClient) -> tuple[str, str]:
    """获取图片验证码并从服务端存储读出答案。返回 (captcha_id, code)。"""
    data = client.get("/api/auth/captcha").json()
    code = captcha_store[data["captcha_id"]][0]
    return data["captcha_id"], code


def register_pending(
    client: TestClient, email: str | None = None, password: str = "pass1234"
) -> dict:
    """注册但未验证邮箱。返回注册响应 JSON（含 dev_code）。"""
    cid, code = solve_captcha(client)
    email = email or f"{uuid.uuid4().hex[:12]}@test.dev"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "captcha_id": cid, "captcha_code": code},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def register_verified(
    client: TestClient, email: str | None = None, password: str = "pass1234"
) -> str:
    """注册并完成邮箱验证。返回 access_token。"""
    pending = register_pending(client, email, password)
    resp = client.post(
        "/api/auth/verify-email", json={"email": pending["email"], "code": pending["dev_code"]}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def login(client: TestClient, email: str, password: str = "pass1234") -> str:
    cid, code = solve_captcha(client)
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password, "captcha_id": cid, "captcha_code": code},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(client: TestClient, email: str | None = None, password: str = "pass1234") -> dict:
    """注册已验证用户并返回 Authorization 头。"""
    token = register_verified(client, email, password)
    return {"Authorization": f"Bearer {token}"}


def new_email() -> str:
    return f"{uuid.uuid4().hex[:12]}@test.dev"


def current_user_id() -> int:
    """当前测试客户端注册的用户（users 表最新一条）。"""
    from app.db import User
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return db.query(User).order_by(User.id.desc()).first().id
    finally:
        db.close()
