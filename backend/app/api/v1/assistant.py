"""
AI 助手模块 — Linux 服务器版本

1. 文档互转: .txt/.docx → PDF, .pdf → .docx
2. 文字转语音: 输入文本 + 选择音色 → 生成语音文件
"""

import os, io, re, tempfile, urllib.parse
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/assistant", tags=["AI助手"])


# ============================================================
# 1. 文档互转
# ============================================================

@router.post("/convert-document")
@router.post("/convert-to-pdf")  # 兼容旧路径
async def convert_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("txt", "docx", "pdf"):
        raise HTTPException(400, f"不支持 .{ext} 格式，仅支持 .txt / .docx / .pdf")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "文件超过 20MB 限制")

    if ext == "pdf":
        # PDF → Word
        docx_bytes = _pdf_to_docx_libreoffice(content, file.filename)
        if docx_bytes is None:
            raise HTTPException(500, "PDF 转 Word 失败，请确保服务器已安装 LibreOffice")
        out_name = file.filename.rsplit(".", 1)[0] + ".docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(out_name)}"
            },
        )

    # txt/docx → PDF
    if ext == "docx":
        pdf_bytes = _docx_to_pdf_libreoffice(content, file.filename)
        if pdf_bytes is None:
            elements = _parse_docx(content)
            pdf_bytes = _generate_pdf(elements, file.filename)
    else:
        text = content.decode("utf-8-sig")
        if not text or len(text.strip()) < 5:
            raise HTTPException(400, f"文档内容过短")
        text = re.sub(r"[​‌‍‎‏  ­﻿]", "", text)
        elements = _text_to_elements(text)
        pdf_bytes = _generate_pdf(elements, file.filename)

    out_name = file.filename.rsplit(".", 1)[0] + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(out_name)}"
        },
    )


def _find_soffice() -> str | None:
    """查找 LibreOffice 可执行文件路径"""
    import subprocess
    soffice_paths = ["soffice", "libreoffice", "/usr/bin/soffice", "/usr/bin/libreoffice"]
    for p in soffice_paths:
        if subprocess.run(["which", p], capture_output=True).returncode == 0:
            return p
    return None


def _docx_to_pdf_libreoffice(content: bytes, filename: str) -> bytes | None:
    """使用 LibreOffice 转换 docx → PDF，完美保留格式"""
    import subprocess
    soffice = _find_soffice() or "soffice"

    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        out_dir = tempfile.mkdtemp()
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, tmp_path],
            timeout=60,
            capture_output=True,
            text=True,
        )
        base = os.path.basename(tmp_path)
        pdf_name = base.rsplit(".", 1)[0] + ".pdf"
        pdf_path = os.path.join(out_dir, pdf_name)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 100:
            with open(pdf_path, "rb") as f:
                return f.read()
        return None
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp_path)
            for f in os.listdir(out_dir):
                os.unlink(os.path.join(out_dir, f))
            os.rmdir(out_dir)
        except Exception:
            pass


def _pdf_to_docx_libreoffice(content: bytes, filename: str) -> bytes | None:
    """使用 pdf2docx 转换 PDF → Word"""
    from loguru import logger

    tmp_pdf = None
    tmp_docx = None
    try:
        from pdf2docx import Converter
    except ImportError:
        logger.error("pdf2docx not installed, run: pip install pdf2docx")
        return None

    try:
        # 写入临时 PDF
        tmp_pdf = tempfile.mktemp(suffix=".pdf")
        tmp_docx = tempfile.mktemp(suffix=".docx")
        with open(tmp_pdf, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        logger.info(f"Converting PDF ({len(content)} bytes) to DOCX via pdf2docx")
        cv = Converter(tmp_pdf)
        cv.convert(tmp_docx)
        cv.close()

        if os.path.exists(tmp_docx) and os.path.getsize(tmp_docx) > 100:
            with open(tmp_docx, "rb") as f:
                return f.read()

        logger.error("pdf2docx conversion failed: no output")
        return None
    except Exception as e:
        logger.error(f"PDF→Word conversion error: {e}")
        return None
    finally:
        for p in [tmp_pdf, tmp_docx]:
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass


def _parse_docx(content: bytes) -> list[dict]:
    from docx import Document
    from io import BytesIO
    try:
        doc = Document(BytesIO(content))
        elements = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                elements.append({"type": "blank"})
                continue
            style_name = (p.style.name if p.style else "").lower()
            is_heading = "heading" in style_name or "title" in style_name
            h_level = 1
            if is_heading:
                for lv in range(1, 7):
                    if f"heading {lv}" in style_name:
                        h_level = lv
                        break
            elements.append({
                "type": "heading" if is_heading else "paragraph",
                "text": text,
                "heading_level": h_level if is_heading else 0,
            })
        return elements
    except Exception:
        raise HTTPException(400, "无法解析 .docx 文件")


def _text_to_elements(text: str) -> list[dict]:
    elements = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            elements.append({"type": "blank"})
        elif len(para) < 60 and (
            para[0].isdigit() or para.startswith("第") or para.startswith("一")
        ):
            elements.append({"type": "heading", "text": para, "heading_level": 2})
        else:
            elements.append({"type": "paragraph", "text": para, "heading_level": 0})
    return elements


def _generate_pdf(elements: list[dict], title: str = "document") -> bytes:
    from fpdf import FPDF
    from datetime import datetime

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    # Use Chinese font if available, fallback to Helvetica
    cn = "Helvetica"
    font_dirs = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    for fp in font_dirs:
        if os.path.exists(fp):
            pdf.add_font("CN", "", fp)
            pdf.add_font("CN", "B", fp)
            cn = "CN"
            break

    # Title
    pdf.set_font(cn, "B", 16)
    pdf.cell(page_w, 12, title.rsplit(".", 1)[0], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(cn, "", 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(page_w, 6, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_text_color(26, 32, 44)

    for elem in elements:
        if elem["type"] == "blank":
            pdf.ln(4)
        elif elem["type"] == "heading":
            size = {1: 16, 2: 14, 3: 13, 4: 12, 5: 11, 6: 10}.get(elem.get("heading_level", 2), 13)
            pdf.set_font(cn, "B", size)
            pdf.ln(3)
            pdf.cell(page_w, size * 0.6, elem["text"][:120], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            pdf.set_font(cn, "", 10)
        else:
            pdf.set_font(cn, "", 10)
            pdf.multi_cell(page_w, 5.5, elem["text"])

    return bytes(pdf.output())


# ============================================================
# 2. 文字转语音
# ============================================================

AVAILABLE_VOICES = [
    {"id": "edge-xiaoxiao", "name": "晓晓 (微软 TTS)", "type": "edge", "gender": "女"},
    {"id": "edge-yunxi", "name": "云希 (微软 TTS)", "type": "edge", "gender": "男"},
    {"id": "edge-xiaoyi", "name": "晓依 (微软 TTS)", "type": "edge", "gender": "女"},
    {"id": "edge-yunjian", "name": "云健 (微软 TTS)", "type": "edge", "gender": "男"},
    {"id": "edge-yunyang", "name": "云扬 (微软 TTS)", "type": "edge", "gender": "男"},
    {"id": "edge-yunxia", "name": "云夏 (微软 TTS)", "type": "edge", "gender": "男"},
    {"id": "edge-liaoning-xiaobei", "name": "晓北(东北话)", "type": "edge", "gender": "女"},
    {"id": "edge-HiuGaai", "name": "晓佳(粤语)", "type": "edge", "gender": "女"},
]

EDGE_VOICE_MAP = {
    "edge-xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "edge-yunxi": "zh-CN-YunxiNeural",
    "edge-xiaoyi": "zh-CN-XiaoyiNeural",
    "edge-yunjian": "zh-CN-YunjianNeural",
    "edge-yunyang": "zh-CN-YunyangNeural",
    "edge-yunxia": "zh-CN-YunxiaNeural",
    "edge-liaoning-xiaobei": "zh-CN-liaoning-XiaobeiNeural",
    "edge-HiuGaai": "zh-HK-HiuGaaiNeural",
}


@router.get("/voices")
async def list_voices(current_user: User = Depends(get_current_user)):
    return {"voices": AVAILABLE_VOICES}


class TTSRequest(BaseModel):
    text: str = Field(min_length=2, max_length=3000)
    voice: str = Field(default="edge-xiaoxiao")


@router.post("/text-to-speech")
async def text_to_speech(
    req: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    if req.voice not in EDGE_VOICE_MAP:
        raise HTTPException(400, f"未知音色: {req.voice}")

    voice_name = EDGE_VOICE_MAP[req.voice]
    buffer = await _tts_edge(req.text, voice_name)
    if buffer:
        return Response(
            content=buffer.read(),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f"attachment; filename={req.voice}.mp3"},
        )
    raise HTTPException(503, "Edge TTS 生成失败")


async def _tts_edge(text: str, voice: str) -> io.BytesIO | None:
    try:
        import edge_tts
        buf = io.BytesIO()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()

        communicate = edge_tts.Communicate(text=text, voice=voice)
        await communicate.save(tmp_path)

        with open(tmp_path, "rb") as f:
            buf.write(f.read())
        os.unlink(tmp_path)
        buf.seek(0)
        if buf.getbuffer().nbytes > 100:
            return buf
    except Exception:
        pass
    return None


# ============================================================
# 3. 文档转语音
# ============================================================

@router.post("/document-to-speech")
async def document_to_speech(
    file: UploadFile = File(...),
    voice: str = Form(default="edge-xiaoxiao"),
    current_user: User = Depends(get_current_user),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("txt", "docx"):
        raise HTTPException(400, f"不支持 .{ext}")

    content = await file.read()
    if ext == "docx":
        elements = _parse_docx(content)
        text = "\n".join(e["text"] for e in elements if e["type"] != "blank")
    else:
        text = content.decode("utf-8-sig")

    if len(text) < 5:
        raise HTTPException(400, "文档内容过短")
    if len(text) > 5000:
        text = text[:5000] + "..."

    req = TTSRequest(text=text, voice=voice)
    return await text_to_speech(req, current_user)
