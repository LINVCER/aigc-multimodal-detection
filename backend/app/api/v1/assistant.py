"""
AI 助手模块

1. 文档转 PDF: 上传 .txt/.docx 文档 → 转换为格式化 PDF
2. 文字转语音: 输入文本 + 选择音色 → 生成语音文件

端点:
  POST /assistant/convert-to-pdf    — 文档转 PDF
  POST /assistant/text-to-speech    — 文字转语音
  GET  /assistant/voices            — 获取可用音色列表
"""

import os, io, re, tempfile, urllib.parse
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/assistant", tags=["AI助手"])


SOFFICE = r"D:/AAA/program/soffice.exe"
# ============================================================
# 1. 文档转 PDF
# ============================================================

@router.post("/convert-to-pdf")
async def convert_to_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传 .txt / .docx 文档，转换为 PDF"""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("txt", "docx"):
        raise HTTPException(400, f"不支持 .{ext} 格式，仅支持 .txt / .docx")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "文件超过 20MB 限制")

    if ext == "docx":
        # Use LibreOffice for perfect fidelity
        if os.path.exists(SOFFICE):
            import subprocess, tempfile
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            out_dir = tempfile.mkdtemp()
            subprocess.run([SOFFICE, '--headless', '--convert-to', 'pdf', '--outdir', out_dir, tmp_path],
                         timeout=30, capture_output=True)
            pdf_name = os.path.basename(tmp_path).replace('.docx', '.pdf')
            pdf_path = os.path.join(out_dir, pdf_name)
            if os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
                os.unlink(tmp_path); os.unlink(pdf_path); os.rmdir(out_dir)
            else:
                os.unlink(tmp_path); os.rmdir(out_dir)
                raise HTTPException(500, 'LibreOffice 转换失败')
        else:
            # Fallback to python-docx + fpdf2
            elements = _parse_docx(content)
            pdf_bytes = _generate_pdf_formatted(elements, file.filename)
    else:
        text = content.decode("utf-8-sig")
        if not text or len(text.strip()) < 5:
            raise HTTPException(400, f"文档内容过短（{len(text.strip())}字符，至少5字符）")
        import re
        text = re.sub(r"[​‌‍‎‏  ­﻿]", "", text)
        pdf_bytes = _text_to_pdf(text, file.filename)

    out_name = file.filename.rsplit(".", 1)[0] + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(out_name)}"},
    )


def _parse_docx(content: bytes):
    from docx import Document
    from io import BytesIO
    try:
        doc = Document(BytesIO(content))
        elements = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                elements.append({'type': 'blank'})
                continue
            style_name = (p.style.name if p.style else '').lower()
            is_heading = 'heading' in style_name or 'title' in style_name or 'toc' in style_name
            h_level = 1
            if is_heading:
                for lv in range(1, 7):
                    if f'heading {lv}' in style_name: h_level = lv; break
            runs = []
            for run in p.runs:
                if run.text.strip():
                    sz = None
                    try:
                        if run.font.size: sz = run.font.size.pt
                    except: pass
                    runs.append({'text': run.text, 'bold': bool(run.bold), 'italic': bool(run.italic), 'size': sz})
            elements.append({'type': 'heading' if is_heading else 'paragraph', 'text': text, 'heading_level': h_level if is_heading else 0, 'runs': runs})
        return elements
    except Exception:
        raise HTTPException(400, '无法解析 .docx 文件')


def _generate_pdf_formatted(elements, title='document'):
    """根据格式化元素生成 PDF (支持 docx 样式)"""
    from fpdf import FPDF
    from datetime import datetime

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    # Chinese font
    font_paths = ['C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simsun.ttc', 'C:/Windows/Fonts/simhei.ttf']
    cn = 'Helvetica'
    for fp in font_paths:
        if os.path.exists(fp):
            pdf.add_font('CN', '', fp, uni=True); pdf.add_font('CN', 'B', fp, uni=True)
            cn = 'CN'; break

    # Title
    pdf.set_font(cn, 'B', 18)
    pdf.cell(page_w, 12, title.rsplit('.', 1)[0], align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font(cn, '', 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(page_w, 6, f'转换时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(8)
    pdf.set_text_color(26, 32, 44)

    for elem in elements:
        if elem['type'] == 'blank':
            pdf.ln(4)
            continue
        elif elem['type'] == 'heading':
            size = {1: 16, 2: 14, 3: 13, 4: 12, 5: 11, 6: 10}.get(elem['heading_level'], 13)
            pdf.set_font(cn, 'B', size)
            pdf.ln(4)
            pdf.cell(page_w, size * 0.6, elem['text'][:80], new_x='LMARGIN', new_y='NEXT')
            pdf.ln(2)
            pdf.set_font(cn, '', 11)
        else:
            pdf.set_font(cn, '', 11)
            # Build paragraph with inline formatting
            if elem.get('runs'):
                pdf.set_font(cn, '', 11)
                line = ''
                for run in elem['runs']:
                    txt = run['text']
                    is_bold = run.get('bold', False)
                    is_italic = run.get('italic', False)
                    style = ''
                    if is_bold and is_italic: style = 'BI'
                    elif is_bold: style = 'B'
                    elif is_italic: style = ''
                    if style:
                        pdf.set_font(cn, style, 11)
                    if line:
                        line += txt
                    else:
                        line = txt
                if line:
                    pdf.multi_cell(page_w, 6.5, line)
            else:
                pdf.multi_cell(page_w, 6.5, elem['text'])

    pdf.ln(6)
    pdf.set_font(cn, '', 8)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(page_w, 8, f'由 AIGC--多模态检测 转换 - {title}', align='C')
    return bytes(pdf.output())


def _text_to_pdf(text: str, title: str = 'document') -> bytes:
    """纯文本转 PDF (兼容 .txt 文件)"""
    elements = []
    for para in text.split(chr(10)):
        para = para.strip()
        if not para:
            elements.append({'type': 'blank'})
        elif len(para) < 50 and (para[0].isdigit() or para.startswith('第') or para.startswith('一')):
            elements.append({'type': 'heading', 'text': para, 'heading_level': 2, 'runs': []})
        else:
            elements.append({'type': 'paragraph', 'text': para, 'heading_level': 0, 'runs': []})
    return _generate_pdf_formatted(elements, title)
# ============================================================
# 2. 文字转语音
# ============================================================

AVAILABLE_VOICES = [
    {"id": "chattts", "name": "ChatTTS (AI合成)", "type": "ai", "samples": 0},
    {"id": "edge-xiaoxiao", "name": "晓晓 (微软 TTS)", "type": "edge", "gender": "女"},
    {"id": "edge-yunxi", "name": "云希 (微软 TTS)", "type": "edge", "gender": "男"},
    {"id": "edge-xiaoyi", "name": "晓依 (微软 TTS)", "type": "edge", "gender": "女"},
    {"id": "edge-yunjian", "name": "云健 (微软 TTS)", "type": "edge", "gender": "男"},
    {"id": "edge-yunyang", "name": "云扬 (微软 TTS)", "type": "edge", "gender": "男"},
    {"id": "edge-yunxia", "name": "云夏 (微软 TTS)", "type": "edge", "gender": "男"},
    {"id": "edge-liaoning-xiaobei", "name": "晓北(东北话)", "type": "edge", "gender": "女"},
    {"id": "edge-HiuGaai", "name": "晓佳(粤语)", "type": "edge", "gender": "女"},
]


@router.get("/voices")
async def list_voices(
    current_user: User = Depends(get_current_user),
):
    """获取可用音色列表"""
    return {"voices": AVAILABLE_VOICES}


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


class TTSRequest(BaseModel):
    text: str = Field(min_length=2, max_length=3000)
    voice: str = Field(default="edge-xiaoxiao")


@router.post("/text-to-speech")
async def text_to_speech(
    req: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    """文字转语音 — 支持 ChatTTS + edge-tts 双引擎"""
    import soundfile as sf
    import numpy as np

    if req.voice == "chattts":
        # Local ChatTTS
        buffer = await _tts_chattts(req.text)
        if buffer:
            return Response(
                content=buffer.read(),
                media_type="audio/wav",
                headers={"Content-Disposition": "attachment; filename=chattts_output.wav"},
            )
        raise HTTPException(503, "ChatTTS 不可用")

    elif req.voice in EDGE_VOICE_MAP:
        # Edge TTS
        voice = EDGE_VOICE_MAP[req.voice]
        buffer = await _tts_edge(req.text, voice)
        if buffer:
            return Response(
                content=buffer.read(),
                media_type="audio/mpeg",
                headers={"Content-Disposition": f"attachment; filename={req.voice}.mp3"},
            )
        raise HTTPException(503, "Edge TTS 生成失败")

    raise HTTPException(400, f"未知音色: {req.voice}")


async def _tts_chattts(text: str) -> io.BytesIO | None:
    """ChatTTS 本地合成"""
    try:
        from ChatTTS import Chat
        import torch

        chat = Chat()
        chat.load(source="custom", custom_path=r"D:\AAA\image_nious\models\audio\chattts_v2")

        params = Chat.InferCodeParams(temperature=0.3)
        wavs = chat.infer([text], use_decoder=True, params_infer_code=params)
        if wavs and len(wavs) > 0:
            audio = wavs[0]
            if isinstance(audio, torch.Tensor):
                audio = audio.cpu().numpy()
            audio = np.squeeze(audio).astype(np.float32)

            buf = io.BytesIO()
            import soundfile as sf
            sf.write(buf, audio, 24000, format="WAV")
            buf.seek(0)
            return buf
    except Exception:
        return None
    return None


async def _tts_edge(text: str, voice: str) -> io.BytesIO | None:
    """Edge TTS 合成"""
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
# 3. 文档转语音（完整文档朗读）
# ============================================================

class DocTTSRequest(BaseModel):
    """文档转语音请求"""
    pass  # Handled via multipart form


@router.post("/document-to-speech")
async def document_to_speech(
    file: UploadFile = File(...),
    voice: str = Form(default="edge-xiaoxiao"),
    current_user: User = Depends(get_current_user),
):
    """上传文档 → 提取文本 → 转语音 → 返回 MP3"""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("txt", "docx"):
        raise HTTPException(400, f"不支持 .{ext}")

    content = await file.read()
    if ext == "docx":
        text = _parse_docx(content)
    else:
        text = content.decode("utf-8-sig")

    if len(text) < 5:
        raise HTTPException(400, "文档内容过短")

    # 限制长度
    if len(text) > 5000:
        text = text[:5000] + "..."

    req = TTSRequest(text=text, voice=voice)
    return await text_to_speech(req, current_user)
