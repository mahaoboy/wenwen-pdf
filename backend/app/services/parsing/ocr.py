"""扫描件 OCR：PaddleOCR 中文识别，输出与 extract_pages 同构的页结构。

PaddleOCR 依赖较重（paddlepaddle），首次加载慢；
MVP 按需懒加载，仅整本无文本层的 PDF 才走此模块。
"""
from __future__ import annotations


def ocr_pages(pdf_path: str) -> list[dict]:
    """逐页 OCR，输出 [{"page", "text", "blocks": [{"text", "bbox", "char_start", "char_end"}]}]。"""
    import fitz  # PyMuPDF（渲染页图片用）

    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("扫描件解析需要 paddleocr：pip install paddleocr paddlepaddle") from exc

    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    pages: list[dict] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=200)
            result = ocr.ocr(pix.tobytes("png"), cls=True)
            blocks: list[dict] = []
            parts: list[str] = []
            offset = 0
            for block in result or []:
                for box, (text, _conf) in block:
                    text = text.strip()
                    if not text:
                        continue
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    if parts:
                        offset += 2  # 块间空行宽度
                    blocks.append(
                        {
                            "text": text,
                            "bbox": [round(min(xs), 1), round(min(ys), 1),
                                     round(max(xs), 1), round(max(ys), 1)],
                            "char_start": offset,
                            "char_end": offset + len(text),
                        }
                    )
                    parts.append(text)
                    offset += len(text)
            pages.append({"page": i, "text": "\n\n".join(parts), "blocks": blocks})
    return pages
