"""数据库模型：用户、文档、对话消息、额度。"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(32), default="free")  # free / buyout / monthly / yearly
    # BYOK：用户自备 DeepSeek API Key（优先于全局配置；MVP 本地部署明文存储，生产需加密）
    deepseek_api_key: Mapped[str] = mapped_column(String(255), default="")
    # 邮箱验证：注册后需验证邮箱才能登录；存量用户迁移时回填为已验证
    email_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    docs: Mapped[list["Document"]] = relationship(back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/parsing/ready/error
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    # 解析完成后由 LLM 生成的文档摘要与动态建议问题（增值首屏；无 Key 时留空）
    summary: Mapped[str] = mapped_column(Text, default="")
    suggestions: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="docs")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    role: Mapped[str] = mapped_column(String(16))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    # 引用映射：JSON 字符串，[{"chunk_id":..., "page":..., "snippet":...}]
    citations: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    document: Mapped["Document"] = relationship(back_populates="messages")


class Chunk(Base):
    """切片：引用溯源的最小单元，位置信息供前端跳转高亮。"""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # {doc_id}-c{序号}
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer, default=0)  # 页内字符偏移
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    bbox_json: Mapped[str] = mapped_column(Text, default="[]")  # [x0, y0, x1, y1]
    text: Mapped[str] = mapped_column(Text)
    snippet: Mapped[str] = mapped_column(String(160), default="")


class QuotaUsage(Base):
    """用户额度用量追踪（提问次数；文档数按 documents 表实时统计）。"""

    __tablename__ = "quota_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class MetricsEvent(Base):
    """轻量监控事件：注册/登录/问答/上传/攻击尝试等，一行一事件。"""

    __tablename__ = "metrics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[str] = mapped_column(Text, default="{}")
