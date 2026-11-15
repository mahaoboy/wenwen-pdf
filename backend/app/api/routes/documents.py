"""文档路由：上传 / 列表 / 删除 + 后台解析流水线（模块1 + 模块2）。"""
import json
import logging
import os
import re
import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db import Chunk, Document, Message, User
from app.db.session import SessionLocal, get_db
from app.schemas import DocumentOut
from app.services.metrics import client_ip, record

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_BACKEND_DIR = Path(__file__).resolve().parents[3]
UPLOAD_DIR = _BACKEND_DIR / "uploads"
ALLOWED_SUFFIX = ".pdf"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9\u4e00-\u9fa5._ -]+")
_UPLOAD_DIR_RESOLVED = str(UPLOAD_DIR.resolve())


def _safe_upload_name(filename: str | None) -> str:
    """上传文件名消毒：剥离路径分量与危险字符，杜绝路径穿越写入。

    历史教训：`u{id}_../../root/.ssh/authorized_keys2` 可逃逸出上传目录，
    配合 root 运行即等于服务器任意文件写（已实测确认，高危）。
    """
    raw = Path(filename or "untitled.pdf").name
    cleaned = _SAFE_NAME_RE.sub("_", raw).strip("._ ") or "untitled.pdf"
    cleaned = cleaned[:120]
    if not cleaned.lower().endswith(ALLOWED_SUFFIX):
        cleaned += ALLOWED_SUFFIX
    return cleaned


def _is_within_uploads(path: Path) -> bool:
    resolved = Path(os.path.normpath(str(path)))
    try:
        resolved.relative_to(_UPLOAD_DIR_RESOLVED)
        return True
    except ValueError:
        return False


# 解析串行队列：1 核小机器上防止多个大 PDF 并发解析挤爆内存
_PARSE_SLOTS = threading.BoundedSemaphore(1)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    docs = db.query(Document).filter(Document.user_id == user.id).order_by(Document.created_at.desc()).all()
    out: list[DocumentOut] = []
    for d in docs:
        try:
            suggestions = json.loads(d.suggestions) if d.suggestions else []
        except ValueError:
            suggestions = []
        out.append(
            DocumentOut(
                id=d.id,
                filename=d.filename,
                status=d.status,
                page_count=d.page_count,
                chunk_count=d.chunk_count,
                summary=d.summary or "",
                suggestions=suggestions,
            )
        )
    return out


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    settings = get_settings()
    doc_count = db.query(Document).filter(Document.user_id == user.id).count()
    limit = settings.free_doc_limit  # TODO(阶段5): 按 user.plan 取对应档位额度
    if doc_count >= limit:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, f"文档数已达上限（{limit}），请升级套餐")

    if not (file.filename or "").lower().endswith(ALLOWED_SUFFIX):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 PDF 文件")

    # 大小限制（应用层；nginx 层另有 client_max_body_size 双重防御）
    max_mb = settings.max_upload_mb
    if file.size and file.size > max_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"文件过大（{file.size / 1024 / 1024:.1f}MB），单个 PDF 不超过 {max_mb}MB",
        )

    UPLOAD_DIR.mkdir(exist_ok=True)
    safe_name = _safe_upload_name(file.filename)
    dest = UPLOAD_DIR / f"u{user.id}_{safe_name}"
    if not _is_within_uploads(dest):  # 双重校验：resolve 后必须仍在上传目录内
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件名不合法")
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = Document(user_id=user.id, filename=safe_name, file_path=str(dest))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 后台流水线：提取 → 切片 → 入库（模块2），完成后 status=ready
    background_tasks.add_task(_parse_document, doc.id)
    record("doc_upload", ip=client_ip(request), user_id=user.id, meta={"filename": doc.filename, "size": file.size or 0})
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        summary=doc.summary or "",
        suggestions=[],
    )


def _parse_document(doc_id: int) -> None:
    """后台流水线：提取（PyMuPDF/PDFPlumber/OCR）→ 条款切片 → 向量索引 → Chunk 入库。

    串行队列：多个上传同时解析时排队执行，保护小内存机器。
    进程重启会丢失队列中的任务——启动时 recover_stuck_documents 自愈。
    """
    with _PARSE_SLOTS:
        _run_parse(doc_id)


def _run_parse(doc_id: int) -> None:
    db = SessionLocal()
    # 幂等清理：重解析场景下移除旧切片与向量，避免重复索引
    db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
    db.commit()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        doc.status = "parsing"
        db.commit()

        from app.services.parsing.chunker import chunk_pages
        from app.services.parsing.extractor import extract_pages

        pages = extract_pages(doc.file_path)
        chunks = chunk_pages(pages, doc.id)
        for c in chunks:
            db.add(
                Chunk(
                    id=c["chunk_id"],
                    document_id=doc.id,
                    seq=int(c["chunk_id"].rsplit("c", 1)[1]),
                    page=c["page"],
                    char_start=c["char_start"],
                    char_end=c["char_end"],
                    bbox_json=json.dumps(c["bbox"]),
                    text=c["own"],  # 落库用切片自身文本（不含重叠前缀），引用文本保持干净
                    snippet=c["snippet"],
                )
            )
        doc.page_count = len(pages)
        doc.chunk_count = len(chunks)
        db.commit()

        # 向量索引（模块3）：失败不阻塞解析（BM25 兜底）
        from app.services.retrieval.hybrid import ensure_index

        ensure_index(doc.id, chunks)

        # 增值首屏：摘要 + 动态建议问题（无 Key / 失败时留空，不阻塞解析）
        from app.services.generation.summary import generate_summary_and_suggestions

        summary, suggestions = generate_summary_and_suggestions(doc.id, chunks)
        doc.summary = summary
        doc.suggestions = json.dumps(suggestions, ensure_ascii=False)
        db.commit()

        doc.status = "ready"
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("文档解析失败 doc_id=%s", doc_id)
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.status = "error"
            db.commit()
    finally:
        db.close()


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    request: Request,
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    # 隐私闸：一键删除，连带清理原文件、切片、消息、向量/BM25 索引与缓存
    stored = Path(doc.file_path)
    if _is_within_uploads(stored):  # 防御旧数据中的穿越路径
        stored.unlink(missing_ok=True)
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.query(Message).filter(Message.document_id == doc.id).delete()
    db.delete(doc)
    db.commit()
    record("doc_delete", ip=client_ip(request), user_id=user.id)  # 先提交释放 SQLite 写锁，再做检索层清理（二次会话 DELETE 避免撞锁）
    from app.services.retrieval.hybrid import delete_doc as delete_retrieval

    delete_retrieval(doc.id)  # 向量索引 + BM25 缓存 + 残余切片（幂等）
    from app.services.cache import invalidate_doc

    invalidate_doc(doc.id)


@router.post("/{doc_id}/reparse", status_code=status.HTTP_202_ACCEPTED)
def reparse_document(
    request: Request,
    doc_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """失败文档自助重解析：error → pending，重新排队后台流水线。"""
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    if doc.status != "error":
        raise HTTPException(status.HTTP_409_CONFLICT, "仅解析失败的文档支持重新解析")

    doc.status = "pending"
    db.commit()
    background_tasks.add_task(_parse_document, doc.id)
    record("doc_reparse", ip=client_ip(request), user_id=user.id, meta={"doc_id": doc_id})
    return {"id": doc.id, "status": "pending"}


def recover_stuck_documents() -> int:
    """启动自愈：进程重启会丢失内存中的解析任务，卡在 pending/parsing 的文档标记为失败。

    返回受影响文档数。用户重新上传即可（原文件可能仍在上传目录，但不自动重试——
    避免重启风暴时反复解析大文件）。
    """
    db = SessionLocal()
    try:
        n = (
            db.query(Document)
            .filter(Document.status.in_(["pending", "parsing"]))
            .update({Document.status: "error"}, synchronize_session=False)
        )
        db.commit()
        if n:
            logger.warning("启动自愈：%d 个文档因进程重启中断解析，已标记为失败，请重新上传", n)
        return n
    finally:
        db.close()
