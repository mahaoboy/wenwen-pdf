"""模块2测试：PDF 提取（PyMuPDF + PDFPlumber 双通道）与条款切片。"""
import fitz
import pytest

from app.services.parsing.chunker import chunk_pages
from app.services.parsing.extractor import _extract_pdfplumber, _extract_pymupdf, extract_pages


def make_pdf_bytes() -> bytes:
    """生成两页测试 PDF（ASCII，避免 Base-14 字体缺 CJK 字形）。"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "1. The Buyer shall pay the price within 30 days.", fontsize=12)
    page.insert_text((72, 130), "This contract becomes effective upon signature.", fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((72, 100), "2. The Seller shall ensure goods meet national standards.", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="module")
def pdf_file(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("pdfs") / "contract.pdf"
    path.write_bytes(make_pdf_bytes())
    return str(path)


def test_extract_pymupdf(pdf_file):
    pages = _extract_pymupdf(pdf_file)
    assert len(pages) == 2
    for i, p in enumerate(pages, start=1):
        assert p["page"] == i
        assert p["text"].strip()
        assert p["blocks"], "每页应有文本块"
        for b in p["blocks"]:
            assert len(b["bbox"]) == 4 and b["bbox"][2] > b["bbox"][0]
            assert 0 <= b["char_start"] < b["char_end"] <= len(p["text"])
            # 块文本应出现在页文本的对应偏移处
            assert p["text"][b["char_start"]:b["char_end"]] == b["text"]


def test_extract_pdfplumber_fallback(pdf_file):
    pages = _extract_pdfplumber(pdf_file)
    assert len(pages) == 2
    assert "Buyer" in pages[0]["text"]
    for p in pages:
        for b in p["blocks"]:
            assert p["text"][b["char_start"]:b["char_end"]] == b["text"]


def test_extract_pages_unified(pdf_file):
    pages = extract_pages(pdf_file)
    assert len(pages) == 2
    assert all(p["blocks"] for p in pages)


def test_chunk_clause_split():
    """中文条款切片：命中条款编号即断片，每片带页码与位置。"""
    pages = [
        {
            "page": 3,
            "text": "第一条 甲方应当按期支付货款。\n违约责任：逾期每日按千分之一计付。\n\n第二条 乙方应当保证货物质量符合国家标准。",
            "blocks": [
                {"text": "第一条 甲方应当按期支付货款。\n违约责任：逾期每日按千分之一计付。",
                 "bbox": [72, 90, 500, 130], "char_start": 0, "char_end": 33},
                {"text": "第二条 乙方应当保证货物质量符合国家标准。",
                 "bbox": [72, 150, 500, 170], "char_start": 35, "char_end": 58},
            ],
        }
    ]
    chunks = chunk_pages(pages, doc_id=42)
    assert [c["chunk_id"] for c in chunks] == ["42-c0", "42-c1"]
    assert chunks[0]["page"] == 3
    assert chunks[0]["text"].startswith("第一条")
    assert chunks[1]["text"].startswith("第二条")
    assert "违约责任" in chunks[0]["text"] and "违约责任" not in chunks[1]["text"]
    # 位置信息：偏移落在页文本范围内，bbox 为块并集
    for c in chunks:
        assert 0 <= c["char_start"] < c["char_end"]
        assert c["bbox"] == [
            min(c["bbox"][0], c["bbox"][2]), min(c["bbox"][1], c["bbox"][3]),
            max(c["bbox"][0], c["bbox"][2]), max(c["bbox"][1], c["bbox"][3]),
        ]
    # 条款边界是语义边界：不拼重叠前缀，引用文本干净
    assert not chunks[1]["text"].startswith("…")


def test_chunk_size_split_overlap():
    """按长度截断（非语义边界）时，下一片带前片结尾重叠。"""
    b1 = "甲方向乙方供应货物一批，质量应当符合国家标准。" * 20  # ~440 字
    b2 = "本协议自双方签字盖章之日起生效，一式两份。" * 8  # ~168 字
    pages = [
        {"page": 1, "text": b1 + "\n\n" + b2, "blocks": [
            {"text": b1, "bbox": [72, 90, 500, 400], "char_start": 0, "char_end": len(b1)},
            {"text": b2, "bbox": [72, 420, 500, 440], "char_start": len(b1) + 2,
             "char_end": len(b1) + 2 + len(b2)},
        ]},
    ]
    chunks = chunk_pages(pages, doc_id=9)
    assert len(chunks) == 2
    assert chunks[0]["text"].startswith("甲方")
    # 尺寸截断 → 第二片带前文重叠
    assert chunks[1]["text"].startswith("…")
    assert "质量应当符合" in chunks[1]["text"][:120]
    assert chunks[1]["text"].split("\n", 1)[1].startswith("本协议")


def test_chunk_numeric_clause_and_stable_ids():
    pages = [
        {"page": 1, "text": "", "blocks": [
            {"text": "1. Buyer shall pay within 30 days.", "bbox": [72, 90, 500, 100],
             "char_start": 0, "char_end": 35},
            {"text": "2. Seller shall deliver within 15 days.", "bbox": [72, 120, 500, 130],
             "char_start": 37, "char_end": 76},
        ]},
    ]
    chunks = chunk_pages(pages, doc_id=7)
    assert [c["chunk_id"] for c in chunks] == ["7-c0", "7-c1"]
    assert chunks[0]["char_start"] == 0
    assert "deliver" in chunks[1]["text"]
