"""应用配置：从环境变量加载。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "文问"
    app_env: str = "dev"
    secret_key: str = "change-me-in-prod"

    database_url: str = "sqlite:///./wenwen.db"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    embedding_model: str = "BAAI/bge-small-zh-v1.5"  # MVP 轻量模型跑通；换 BAAI/bge-m3 仅改配置
    embedding_dim: int = 512

    allowed_origins_raw: str = "http://localhost:3000"  # 逗号分隔；同源部署（nginx）时 CORS 不生效

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins_raw.split(",") if o.strip()]

    wechat_pay_mch_id: str = ""
    wechat_pay_api_key: str = ""
    alipay_app_id: str = ""
    alipay_private_key: str = ""

    free_doc_limit: int = 3
    free_question_limit: int = 20
    buyout_doc_limit: int = 100
    buyout_question_limit: int = 200
    sub_monthly_doc_limit: int = 300
    sub_monthly_question_limit: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()
