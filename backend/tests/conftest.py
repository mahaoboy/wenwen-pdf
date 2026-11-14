"""测试环境隔离：真实 .env 的全局 Key 不进测试（需要 Key 的用例在用例内自行设置）。"""
import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_global_llm_key():
    settings = get_settings()
    old = settings.deepseek_api_key
    settings.deepseek_api_key = ""
    yield
    settings.deepseek_api_key = old


@pytest.fixture()
def client():
    """注册一个已验证用户并注入 Authorization 头的测试客户端。"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        from tests.helpers import register_verified

        token = register_verified(c)
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


@pytest.fixture(autouse=True)
def _isolate_email_transport():
    """测试默认禁用真实邮件通道（gmail_api/smtp），需要发信的用例自行设置。"""
    settings = get_settings()
    old_transport = settings.email_transport
    old_smtp_host = settings.smtp_host
    settings.email_transport = ""
    settings.smtp_host = ""
    yield
    settings.email_transport = old_transport
    settings.smtp_host = old_smtp_host
