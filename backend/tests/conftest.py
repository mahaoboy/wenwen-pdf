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
