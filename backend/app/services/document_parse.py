"""Document parsing: pdf / docx / doc -> plain text + LLM structured extraction."""
import json
import re
from pathlib import Path

from app.core.config import get_settings
from app.rag.client import get_sf_client

settings = get_settings()

EXTRACT_SYSTEM_PROMPT = """你是合同信息抽取助手。从合同文本中抽取甲乙方与金额，严格输出 JSON：
{"party_a": "甲方名称", "party_b": "乙方名称", "amount": "数字字符串或空"}
规则：只抽取文本中明确出现的名称与金额；无法识别时输出空字符串；不要编造。"""


def extract_text_from_pdf(path: str) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
    return "\n".join(parts)


def extract_text_from_docx(path: str) -> str:
    from docx import Document

    doc = Document(path)
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def extract_text_from_doc(path: str) -> str:
    """.doc 转 .docx 需要 LibreOffice；失败时返回空并记录。"""
    import subprocess

    out = str(Path(path).with_suffix(".docx"))
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "docx", "--outdir", str(Path(path).parent), path],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return extract_text_from_docx(out)
    except Exception:
        return ""


def parse_document(path: str, file_type: str) -> str:
    ft = file_type.lower()
    if ft == "pdf":
        return extract_text_from_pdf(path)
    if ft == "docx":
        return extract_text_from_docx(path)
    if ft == "doc":
        return extract_text_from_doc(path)
    return ""


async def extract_contract_info(text: str) -> dict:
    """LLM 抽取甲乙方与金额；失败降级返回空字段。"""
    try:
        client = get_sf_client()
        raw = await client.chat(
            [
                {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": f"合同文本（截取前 12000 字）：\n{text[:12000]}"},
            ],
            model=settings.llm_chat_model,
            temperature=0.1,
        )
        data = _parse_json(raw)
        amount = data.get("amount", "")
        return {
            "party_a": _clean(data.get("party_a", "")),
            "party_b": _clean(data.get("party_b", "")),
            "amount": float(re.sub(r"[^\d.]", "", amount)) if amount else 0.0,
        }
    except Exception:
        return {"party_a": "", "party_b": "", "amount": 0.0}


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            return json.loads(match.group(0))
        return {}


def _clean(val: str) -> str:
    val = (val or "").strip()
    if len(val) > 300 or "{未识别}" in val:
        return ""
    return val
