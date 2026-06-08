"""3.F：剧本文件提取——上传文件字节流 → 纯文本 raw_text。

公共 API：
  UnsupportedFormatError  不支持的文件格式（调用方转 415/422）。
  ExtractError            文件损坏/解析失败（调用方转 422）。
  extract_text            按扩展名分流提取纯文本。

设计依据：
  docs/specs/2026-06-03-script-import-sp-pipeline.md §6 / §7
  「三条输入提取层不同，汇入解析器同一入口」——本模块是「上传」这条的提取层，
  产出 raw_text 后交给 run_sp_parse（3.B），不分场、不结构化（那是解析器的职责）。

格式分流：
  .txt / .md  → UTF-8（失败回落 GB18030，兼容 Windows 中文台本）解码，原样返回。
                markdown 不剥语法：Gemma 解析吃 raw，# / * 等标记由 LLM 容错。
  .docx       → python-docx，段落文本按换行拼接（保留空行，利于解析器空行切块）。
  .pdf        → pypdf，逐页 extract_text 后按换行拼接。

不做的事（交下游）：
  - 分场 / 行结构化（run_sp_parse，3.B）
  - 空文本 422 判定（端点，3.D；本模块只在提取彻底失败时抛 ExtractError）
"""

from __future__ import annotations

import io
from pathlib import Path

# 支持的扩展名（小写，含点）。端点据此先行校验，给出明确 415/422。
SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".markdown", ".docx", ".pdf"})


class UnsupportedFormatError(Exception):
    """文件扩展名不在 SUPPORTED_EXTENSIONS。"""


class ExtractError(Exception):
    """文件损坏或解析库抛错（cause 串联原始异常）。"""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


def _decode_text(data: bytes) -> str:
    """纯文本解码：优先 UTF-8（含 BOM），失败回落 GB18030。

    GB18030 是 GBK 超集，覆盖简繁中文，几乎不会 raise——作为兜底解码，
    保证 Windows 上用记事本/旧编辑器存的中文 .txt 也能读。
    """
    # utf-8-sig 自动剥 BOM；非 BOM 文件行为与 utf-8 一致
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("gb18030", errors="replace")


def _extract_docx(data: bytes) -> str:
    """python-docx 提取所有段落文本，按换行拼接（保留空段落）。"""
    try:
        from docx import Document  # 延迟 import：仅 docx 路径加载 lxml
    except ImportError as exc:  # pragma: no cover - 依赖缺失保护
        raise ExtractError("python-docx 未安装，无法解析 .docx", cause=exc) from exc

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # python-docx 对损坏文件抛多种异常
        raise ExtractError("无法打开 .docx 文件（可能已损坏）", cause=exc) from exc

    return "\n".join(p.text for p in document.paragraphs)


def _extract_pdf(data: bytes) -> str:
    """pypdf 逐页提取文本，按换行拼接。"""
    try:
        from pypdf import PdfReader  # 延迟 import
    except ImportError as exc:  # pragma: no cover
        raise ExtractError("pypdf 未安装，无法解析 .pdf", cause=exc) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ExtractError("无法解析 .pdf 文件（可能已损坏或加密）", cause=exc) from exc

    return "\n".join(pages)


def extract_text(filename: str, data: bytes) -> str:
    """按 filename 扩展名提取纯文本，返回 raw_text（交 run_sp_parse）。

    Args:
        filename: 原始文件名（仅用扩展名分流，大小写不敏感）。
        data:     文件字节内容。

    Returns:
        提取出的纯文本（未做空白裁剪——交解析器/端点判空）。

    Raises:
        UnsupportedFormatError: 扩展名不支持。
        ExtractError:           解析库打开/读取失败。
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(f"不支持的文件格式：{ext or '(无扩展名)'}")

    if ext == ".docx":
        return _extract_docx(data)
    if ext == ".pdf":
        return _extract_pdf(data)
    # .txt / .md / .markdown
    return _decode_text(data)
