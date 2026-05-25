"""文档解析 — 支持 txt / docx / pdf"""
import io


def parse_document(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "txt":
        return content.decode("utf-8", errors="replace")

    if ext == "docx":
        from docx import Document
        doc = Document(io.BytesIO(content))
        return "\n\n".join(p.text for p in doc.paragraphs)

    if ext == "pdf":
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    raise ValueError(f"不支持的文件类型: .{ext} (支持 txt/docx/pdf)")
