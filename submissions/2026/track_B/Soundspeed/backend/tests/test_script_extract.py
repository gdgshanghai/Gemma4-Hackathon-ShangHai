"""3.F 文件提取单测：backend/core/script_extract.py。

覆盖：txt/md UTF-8 + BOM + GB18030 回落、docx 往返、不支持格式、损坏文件报错。
PDF 内容提取不在此造真 PDF（需 reportlab 等写库），仅测损坏 → ExtractError；
真 PDF 端到端在 smoke / 手测覆盖。
"""

from __future__ import annotations

import io

import pytest

from backend.core.script_extract import (
    ExtractError,
    UnsupportedFormatError,
    extract_text,
)


def test_txt_utf8():
    raw = "内 咖啡馆 日\n罗湘：我们先聊聊。"
    assert extract_text("script.txt", raw.encode("utf-8")) == raw


def test_txt_utf8_bom_stripped():
    raw = "场3\n角色：台词"
    data = raw.encode("utf-8-sig")  # 带 BOM
    assert extract_text("a.txt", data) == raw  # BOM 被剥


def test_md_treated_as_text():
    raw = "# 第一场\n罗湘：带 markdown 标记的台词"
    # .md 不剥语法，原样返回（LLM 容错）
    assert extract_text("script.md", raw.encode("utf-8")) == raw


def test_markdown_extension():
    raw = "正文"
    assert extract_text("a.markdown", raw.encode("utf-8")) == raw


def test_gb18030_fallback():
    raw = "罗湘：你好世界"
    data = raw.encode("gb18030")  # 非 UTF-8 的中文编码
    # 不抛异常，回落 GB18030 正确解码
    assert extract_text("legacy.txt", data) == raw


def test_unsupported_extension_raises():
    with pytest.raises(UnsupportedFormatError):
        extract_text("script.rtf", b"whatever")


def test_no_extension_raises():
    with pytest.raises(UnsupportedFormatError):
        extract_text("README", b"whatever")


def test_docx_roundtrip():
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("内 咖啡馆 日")
    document.add_paragraph("罗湘：我们先聊聊。")
    document.add_paragraph("（罗湘坐下）")
    buf = io.BytesIO()
    document.save(buf)

    out = extract_text("script.docx", buf.getvalue())
    assert "内 咖啡馆 日" in out
    assert "罗湘：我们先聊聊。" in out
    assert "罗湘坐下" in out
    # 段落按换行拼接
    assert out.split("\n")[0] == "内 咖啡馆 日"


def test_docx_corrupt_raises():
    with pytest.raises(ExtractError):
        extract_text("bad.docx", b"not a real docx")


def test_pdf_corrupt_raises():
    with pytest.raises(ExtractError):
        extract_text("bad.pdf", b"not a real pdf")
