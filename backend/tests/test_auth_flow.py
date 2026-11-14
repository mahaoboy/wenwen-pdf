"""认证流程测试：图片验证码 / 邮箱验证 / 邮箱唯一。"""
import pytest

from tests.helpers import new_email, register_pending, register_verified, solve_captcha


def test_captcha_endpoint_returns_image(client):
    data = client.get("/api/auth/captcha").json()
    assert data["captcha_id"]
    assert data["image"].startswith("data:image/png;base64,")


def test_register_requires_valid_captcha(client):
    cid, _ = solve_captcha(client)
    resp = client.post(
        "/api/auth/register",
        json={"email": new_email(), "password": "pass1234", "captcha_id": cid, "captcha_code": "XXXX"},
    )
    assert resp.status_code == 400
    assert "验证码" in resp.json()["detail"]


def test_captcha_is_single_use(client):
    cid, code = solve_captcha(client)
    ok = client.post(
        "/api/auth/register",
        json={"email": new_email(), "password": "pass1234", "captcha_id": cid, "captcha_code": code},
    )
    assert ok.status_code == 200
    # 同一个验证码第二次使用 → 拒绝
    reused = client.post(
        "/api/auth/register",
        json={"email": new_email(), "password": "pass1234", "captcha_id": cid, "captcha_code": code},
    )
    assert reused.status_code == 400


def test_register_dev_mode_returns_code_and_requires_verification(client):
    """SMTP 未配置（开发模式）：注册返回 dev_code，未验证前不能登录。"""
    email = new_email()
    pending = register_pending(client, email)
    assert pending["verification_required"] is True
    assert pending["smtp_configured"] is False
    assert pending["dev_code"] and len(pending["dev_code"]) == 6

    # 未验证 → 登录 403
    cid, code = solve_captcha(client)
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": "pass1234", "captcha_id": cid, "captcha_code": code},
    )
    assert resp.status_code == 403
    assert "未验证" in resp.json()["detail"]


def test_verify_and_login_flow(client):
    email = new_email()
    pending = register_pending(client, email)

    # 错误验证码
    bad = client.post("/api/auth/verify-email", json={"email": email, "code": "000000"})
    assert bad.status_code == 400

    # 正确验证码 → 直接发 token
    ok = client.post("/api/auth/verify-email", json={"email": email, "code": pending["dev_code"]})
    assert ok.status_code == 200
    token = ok.json()["access_token"]

    # 验证后登录成功
    from tests.helpers import login

    assert login(client, email)


def test_duplicate_email_rejected(client):
    email = new_email()
    register_verified(client, email)  # 已验证用户

    from tests.helpers import register_pending

    resp_body = None
    try:
        pending = register_pending(client, email)
        resp_body = pending  # 若通过则断言失败
    except AssertionError as e:
        resp_body = str(e)
    assert "已注册" in str(resp_body)


def test_unverified_email_still_blocks_reregistration(client):
    """未验证的注册也占用邮箱：同邮箱再次注册 → 提示去完成验证。"""
    email = new_email()
    register_pending(client, email)
    try:
        register_pending(client, email)
        raise AssertionError("重复注册应被拒绝")
    except AssertionError as e:
        assert "未验证" in str(e) or "已注册" in str(e)


def test_resend_returns_new_code(client):
    email = new_email()
    pending = register_pending(client, email)
    # 清除重发冷却（生产由 60s 冷却限制，429 路径由冷却逻辑保证）
    from app.services.email_codes import _last_issue

    _last_issue.pop(email, None)
    # 重发需要图片验证码；code 字段为邮箱验证码占位（重发逻辑不使用）
    cid, code = solve_captcha(client)
    resp = client.post(
        "/api/auth/resend",
        json={"email": email, "code": "", "captcha_id": cid, "captcha_code": code},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verification_required"] is True
    assert body["dev_code"] and len(body["dev_code"]) == 6
    assert body["dev_code"] != pending["dev_code"]  # 新码
