"""简历文件 → 纯文本。PDF 用 pdfplumber，DOCX 用 python-docx，txt/md 直接解码。"""

import io
from pathlib import Path


class ResumeParseError(ValueError):
    pass


ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise ResumeParseError(f"不支持的文件类型 {suffix or '(无后缀)'}，请上传 PDF / DOCX / TXT / MD")

    if suffix == ".pdf":
        return _extract_pdf(data)
    if suffix == ".docx":
        return _extract_docx(data)
    return _decode_text(data)


def _extract_pdf(data: bytes) -> str:
    import pdfplumber

    pages: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
    except Exception as exc:  # noqa: BLE001
        raise ResumeParseError(f"PDF 解析失败：{exc}") from exc
    text = "\n".join(pages).strip()
    if len(text) < 20:
        raise ResumeParseError("未能从 PDF 中提取到有效文本（可能是扫描件或双栏排版），请改用文本粘贴")
    return text


def _extract_docx(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ResumeParseError(f"DOCX 解析失败：{exc}") from exc
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))
    text = "\n".join(paragraphs).strip()
    if len(text) < 20:
        raise ResumeParseError("未能从 DOCX 中提取到有效文本，请改用文本粘贴")
    return text


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "utf-16"):
        try:
            text = data.decode(encoding).strip()
            if text:
                return text
        except UnicodeDecodeError:
            continue
    raise ResumeParseError("文本解码失败，请使用 UTF-8 编码")
