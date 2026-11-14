"""文档路由：上传 / 列表 / 删除 + 后台解析流水线（模块1 + 模块2）。"""
import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db import Chunk, Document, User
from app.db.session import SessionLocal, get_db
from app.schemas import DocumentOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_BACKEND_DIR = Path(__file__).resolve().parents[3]
UPLOAD_DIR = _BACKEND_DIR / "uploads"
ALLOWED_SUFFIX = ".pdf"


@router.get("", response_model=list[DocumentOut])
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    return db.query(Document).filter(Document.user_id == user.id).order_by(Document.created_at.desc()).all()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    settings = get_settings()
    doc_count = db.query(Document).filter(Document.user_id == user.id).count()
    limit = settings.free_doc_limit  # TODO(阶段5): 按 user.plan 取对应档位额度
    if doc_count >= limit:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, f"文档数已达上限（{limit}），请升级套餐")

    if not (file.filename or "").lower().endswith(ALLOWED_SUFFIX):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 PDF 文件")

    UPLOAD_DIR.mkdir(exist_ok=True)
    dest = UPLOAD_DIR / f"u{user.id}_{file.filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = Document(user_id=user.id, filename=file.filename or "untitled.pdf", file_path=str(dest))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 后台流水线：提取 → 切片 → 入库（模块2），完成后 status=ready
    background_tasks.add_task(_parse_document, doc.id)
    return doc


def _parse_document(doc_id: int) -> None:
    """后台流水线：提取（PyMuPDF/PDFPlumber/OCR）→ 条款切片 → Chunk 入库。"""
    db = SessionLocal()
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
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    # 隐私闸：一键删除，连带清理原文件、切片、向量/BM25 索引与缓存
    Path(doc.file_path).unlink(missing_ok=True)
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.delete(doc)
    db.commit()  # 先提交释放 SQLite 写锁，再做检索层清理（二次会话 DELETE 避免撞锁）
    from app.services.retrieval.hybrid import delete_doc as delete_retrieval

    delete_retrieval(doc.id)  # 向量索引 + BM25 缓存 + 残余切片（幂等）
    from app.services.cache import invalidate_doc

    invalidate_doc(doc.id)
