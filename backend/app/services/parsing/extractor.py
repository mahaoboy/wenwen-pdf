"""PDF 文本提取：PyMuPDF 为主、PDFPlumber 兜底，扫描件走 PaddleOCR。

统一输出页结构（位置信息契约，供切片器与前端跳转使用）：
    [{"page": 页码(1起),
      "text": 重建后的整页文本（块按阅读序连接）,
      "blocks": [{"text": 块文本, "bbox": [x0, y0, x1, y1],
                  "char_start": 块在页文本中的起始偏移, "char_end": 结束偏移}]}]
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCAN_TEXT_THRESHOLD = 20  # 整页文本低于该字符数视为疑似扫描页


def extract_pages(pdf_path: str | Path) -> list[dict]:
    """按页提取文本与块位置。降级链：PyMuPDF → PDFPlumber → PaddleOCR。"""
    try:
        pages = _extract_pymupdf(str(pdf_path))
    except Exception as exc:  # 文件损坏/加密等，换 PDFPlumber 兜底
        logger.warning("PyMuPDF 提取失败(%s)，降级 PDFPlumber：%s", type(exc).__name__, pdf_path)
        pages = _extract_pdfplumber(str(pdf_path))

    if pages and all(not p["blocks"] for p in pages):
        # 整本无文本层 → 扫描件，走 OCR
        pages = _extract_ocr(str(pdf_path))
    return pages


def _extract_pymupdf(pdf_path: str) -> list[dict]:
    import fitz  # PyMuPDF

    pages: list[dict] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            raw = page.get_text("dict")
            blocks: list[dict] = []
            parts: list[str] = []
            offset = 0
            for block in raw.get("blocks", []):
                if block.get("type") != 0:  # 只处理文本块，图片块留给 OCR
                    continue
                text = "\n".join(
                    span["text"]
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                ).strip()
                if not text:
                    continue
                if parts:
                    offset += 2  # 块间空行宽度
                blocks.append(
                    {
                        "text": text,
                        "bbox": [round(v, 1) for v in block["bbox"]],
                        "char_start": offset,
                        "char_end": offset + len(text),
                    }
                )
                parts.append(text)
                offset += len(text)
            pages.append({"page": i, "text": "\n\n".join(parts), "blocks": blocks})
    return pages


def _extract_pdfplumber(pdf_path: str) -> list[dict]:
    """PDFPlumber 兜底：按词坐标聚合行，再按行距聚合成块，同样输出位置信息。"""
    import pdfplumber

    pages: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
            blocks = _words_to_blocks(words)
            parts = [b["text"] for b in blocks]
            pages.append({"page": i, "text": "\n\n".join(parts), "blocks": blocks})
    return pages


def _words_to_blocks(words: list[dict]) -> list[dict]:
    """词 → 行（top 相近）→ 块（行距 < 1.5 倍行高则合并），带 bbox 与页内字符偏移。"""
    if not words:
        return []
    words = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))

    # 词 → 行
    lines: list[list[dict]] = []
    cur: list[dict] = [words[0]]
    for w in words[1:]:
        if abs(w["top"] - cur[-1]["top"]) <= 3:
            cur.append(w)
        else:
            lines.append(cur)
            cur = [w]
    lines.append(cur)

    line_objs: list[dict] = []
    for ws in lines:
        ws = sorted(ws, key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ws).strip()
        if not text:
            continue
        line_objs.append(
            {
                "text": text,
                "bbox": [min(w["x0"] for w in ws), min(w["top"] for w in ws),
                         max(w["x1"] for w in ws), max(w["bottom"] for w in ws)],
            }
        )

    # 行 → 块（行距突增即断块），最后统一分配字符偏移
    groups: list[list[dict]] = []
    group: list[dict] = []
    for line in line_objs:
        if group:
            prev = group[-1]
            gap = line["bbox"][1] - prev["bbox"][3]
            line_h = max(prev["bbox"][3] - prev["bbox"][1], 1)
            if gap > line_h * 1.5:
                groups.append(group)
                group = []
        group.append(line)
    if group:
        groups.append(group)

    blocks: list[dict] = []
    offset = 0
    for gi, g in enumerate(groups):
        text = "\n".join(line["text"] for line in g)
        if gi > 0:
            offset += 2  # 块间空行宽度
        blocks.append(
            {
                "text": text,
                "bbox": [
                    min(line["bbox"][0] for line in g),
                    min(line["bbox"][1] for line in g),
                    max(line["bbox"][2] for line in g),
                    max(line["bbox"][3] for line in g),
                ],
                "char_start": offset,
                "char_end": offset + len(text),
            }
        )
        offset += len(text)
    return blocks


def _extract_ocr(pdf_path: str) -> list[dict]:
    """扫描件：PaddleOCR（懒加载，依赖较重）。"""
    from app.services.parsing.ocr import ocr_pages

    return ocr_pages(pdf_path)
