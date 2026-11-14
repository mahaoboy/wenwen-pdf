"""FastAPI 入口：挂载路由、建表、健康检查。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, billing, chat, documents, settings
from app.core.config import get_settings
from app.db import Base
from app.db.session import engine, ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    yield


app = FastAPI(title="文问 WenWen", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": "文问 WenWen"}
