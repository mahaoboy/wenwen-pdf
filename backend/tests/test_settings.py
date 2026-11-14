"""BYOK 设置测试：保存/脱敏/校验/优先级。"""
import pytest

from app.services.generation import answer as answer_svc
from app.services.generation import llm as llm_svc


def test_save_and_status_masked(client):
    resp = client.put("/api/settings/llm", json={"deepseek_api_key": "sk-abcdefghijklmnop1234"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True and data["mode"] == "user"
    assert data["masked"].startswith("sk-abc") and data["masked"].endswith("1234")
    assert "abcdefghijklmnop" not in data["masked"]  # 明文不外泄

    status = client.get("/api/settings/llm").json()
    assert status["configured"] is True and status["mode"] == "user"


def test_clear_key(client):
    client.put("/api/settings/llm", json={"deepseek_api_key": "sk-abcdefghijklmnop1234"})
    resp = client.put("/api/settings/llm", json={"deepseek_api_key": ""})
    assert resp.json()["configured"] is False and resp.json()["mode"] == "extractive"


def test_invalid_key_format_rejected(client):
    resp = client.put("/api/settings/llm", json={"deepseek_api_key": "not-a-key"})
    assert resp.status_code == 400


def test_user_key_takes_priority(client, monkeypatch):
    """用户 Key 优先于全局 Key：chat_generation 应使用用户 Key 调用。"""
    from app.core.config import get_settings

    settings = get_settings()
    old = settings.deepseek_api_key
    settings.deepseek_api_key = "sk-global-key"
    client.put("/api/settings/llm", json={"deepseek_api_key": "sk-user-own-key"})

    captured = {}

    def fake_completion(messages, api_key=None, temperature=0.1):
        captured["api_key"] = api_key
        return "按文档回答 [不校验]"

    monkeypatch.setattr(llm_svc, "chat_completion", fake_completion)
    monkeypatch.setattr(answer_svc.llm, "chat_completion", fake_completion)

    try:
        # 无文档场景只验证 generate_answer 的 Key 优先级（直接调服务层）
        from app.services.generation.answer import generate_answer

        out = generate_answer("问题", [], [], user_api_key="sk-user-own-key")
        assert out["mode"] == "llm"
        assert captured["api_key"] == "sk-user-own-key"

        # 无用户 Key 时回落全局
        out2 = generate_answer("问题", [], [], user_api_key="")
        assert out2["mode"] == "llm" and captured["api_key"] == "sk-global-key"
    finally:
        settings.deepseek_api_key = old


def test_verify_key_endpoint(client, monkeypatch):
    """校验接口：有效/无效两条路径（mock 网络调用）。"""
    class FakeModels:
        data = [type("M", (), {"id": "deepseek-chat"})()]

    class FakeClient:
        def __init__(self, *a, **k):
            self.models = type("M", (), {"list": lambda self: FakeModels()})()

    import app.api.routes.settings as settings_routes

    monkeypatch.setattr(settings_routes, "OpenAI", FakeClient)
    ok = client.post("/api/settings/llm/verify", json={"deepseek_api_key": "sk-valid"}).json()
    assert ok["ok"] is True

    def bad_client(*a, **k):
        raise RuntimeError("401")

    monkeypatch.setattr(settings_routes, "OpenAI", bad_client)
    bad = client.post("/api/settings/llm/verify", json={"deepseek_api_key": "sk-bad"}).json()
    assert bad["ok"] is False
