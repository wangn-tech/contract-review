"""多引擎文档解析：格式回退链 + 可选 OCR + 结构抽取。

引擎链（有序，失败/空文本自动降级下一引擎）：
  1. pdfplumber  —— PDF 文本层（基线，轻量）
  2. pymupdf     —— PDF 文本层（更强版面抽取）
  3. pypdf       —— PDF 纯文本兜底
  4. python-docx —— .docx 段落+表格
  5. LibreOffice —— .doc/.docx 转换兜底（系统依赖，可选）
  6. OCR(pdf2image+pytesseract) —— 扫描件 OCR（可选，需 poppler+tesseract）
  7. DeepSeek OCR —— API OCR（可选，配置 DEEPSEEK_OCR_* 后启用）
  8. Docling / MinerU —— 复杂版面深度解析（可选，extra: docling / mineru）

设计要点：每个引擎独立 try/except；仅接受非空文本；OCR 等重型引擎做成特性开关，
未安装依赖/未配置时静默跳过——保证 Docker 镜像默认体积可控。
"""
import json
import logging
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger("document.parse")
settings = get_settings()

EXTRACT_SYSTEM_PROMPT = """你是合同信息抽取助手。从合同文本中抽取甲乙方与金额，严格输出 JSON：
{"party_a": "甲方名称", "party_b": "乙方名称", "amount": "数字字符串或空"}
规则：只抽取文本中明确出现的名称与金额；无法识别时输出空字符串；不要编造。"""


def _clean(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()


def _parse_pdfplumber(path: str) -> str:
    import pdfplumber

    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
            for table in page.extract_tables() or []:
                for row in table:
                    parts.append(" | ".join(c or "" for c in row))
    return "\n".join(parts)


def _parse_pymupdf(path: str) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    return "\n".join(page.get_text("text") for page in doc)


def _parse_pypdf(path: str) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def _parse_docx(path: str) -> str:
    import docx

    d = docx.Document(path)
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


def _parse_libreoffice(path: str, out_dir: Path) -> str:
    """.doc 等旧格式：LibreOffice 转 txt。"""
    if shutil.which("soffice") is None and shutil.which("libreoffice") is None:
        raise RuntimeError("LibreOffice not installed")
    bin_ = shutil.which("soffice") or shutil.which("libreoffice")
    subprocess.run([bin_, "--headless", "--convert-to", "txt:Text", "--outdir", str(out_dir), path],
                   check=True, capture_output=True, timeout=120)
    txt = out_dir / (Path(path).stem + ".txt")
    if not txt.exists():
        raise RuntimeError("LibreOffice convert failed")
    return txt.read_text(encoding="utf-8", errors="ignore")


def _parse_ocr(path: str, out_dir: Path) -> str:
    """扫描件 OCR：pdf2image + pytesseract。需系统 poppler-utils 与 tesseract。"""
    if shutil.which("pdftoppm") is None or shutil.which("tesseract") is None:
        raise RuntimeError("OCR system deps missing (poppler/tesseract)")
    import pytesseract
    from pdf2image import convert_from_path

    parts = []
    for i, img in enumerate(convert_from_path(path, dpi=200)):
        parts.append(pytesseract.image_to_string(img, lang=settings.ocr_lang or "chi_sim"))
        if i >= 9:  # 上限 10 页，防长文档超时
            break
    return "\n".join(parts)


def _parse_deepseek_ocr(path: str) -> str:
    """DeepSeek OCR（OpenAI-compatible API）：配置 DEEPSEEK_OCR_API_KEY 后启用。"""
    import base64

    from app.rag.client import get_sf_client

    if not settings.deepseek_ocr_api_key:
        raise RuntimeError("deepseek OCR not configured")
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/pdf;base64,{b64}"}},
        {"type": "text", "text": "请完整识别此 PDF 合同文件的全部文字内容，保留段落结构。"},
    ]}]
    get_sf_client()
    import httpx
    resp = httpx.post(
        f"{settings.siliconflow_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.deepseek_ocr_api_key}"},
        json={"model": settings.deepseek_ocr_model, "messages": messages, "max_tokens": 4096},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_docling(path: str) -> str:
    """Docling：复杂版面/表格结构化（重型，需 pip install docling）。"""
    from docling.document_converter import DocumentConverter

    result = DocumentConverter().convert(path)
    return result.document.export_to_markdown()


def _parse_mineru(path: str) -> str:
    """MinerU：PDF 深度解析（重型，需 pip install mineru / magic-pdf）。"""
    from magic_pdf.data.data_reader_writer import FileBasedDataReader
    from magic_pdf.data.dataset import PymuDocDataset

    ds = PymuDocDataset(FileBasedDataReader("").read(path), path)
    result = ds.apply(ds.pipe_txt_mode if hasattr(ds, "pipe_txt_mode") else ds.pipe_ocr_mode)
    return "\n".join(result.get_content_list() or [])


# 引擎注册表：名称 -> 可调用（返回文本）
def _registry():
    enabled = [e.strip() for e in settings.doc_parser_engines.split(",") if e.strip()]
    eng = {
        "pdfplumber": _parse_pdfplumber,
        "pymupdf": _parse_pymupdf,
        "pypdf": _parse_pypdf,
        "docx": _parse_docx,
        "libreoffice": _parse_libreoffice,
        "ocr": _parse_ocr,
        "deepseek_ocr": _parse_deepseek_ocr,
        "docling": _parse_docling,
        "mineru": _parse_mineru,
    }
    return {k: v for k, v in eng.items() if k in enabled}


def extract_text_from_file(path: str, suffix: str | None = None) -> str:
    """按文件后缀选择引擎子链，逐级降级直到得到非空文本。"""
    suffix = (suffix or Path(path).suffix).lower().lstrip(".")
    out_dir = Path(settings.oss_bucket_dir) / "libreoffice"
    out_dir.mkdir(parents=True, exist_ok=True)
    registry = _registry()

    if suffix == "pdf":
        chain = ["pdfplumber", "pymupdf", "pypdf", "docling", "mineru", "ocr", "deepseek_ocr"]
    elif suffix in ("docx", "doc"):
        chain = ["docx", "libreoffice", "docling"]
    elif suffix in ("txt", "md"):
        return _clean(Path(path).read_text(encoding="utf-8", errors="ignore"))
    else:
        chain = ["docx", "libreoffice"]

    for name in chain:
        fn = registry.get(name)
        if fn is None:
            continue
        try:
            text = fn(path, out_dir) if name == "libreoffice" or name == "ocr" else fn(path)
            text = _clean(text)
            if len(text) >= 30:
                logger.info("parse ok: engine=%s suffix=%s len=%d", name, suffix, len(text))
                return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("parse engine %s failed for %s: %s", name, suffix, exc)
    raise ValueError(f"所有解析引擎均失败或文本为空: {path}")


def extract_text_from_pdf(path: str) -> str:
    """兼容旧调用。"""
    return extract_text_from_file(path, "pdf")


def extract_contract_meta(text: str) -> dict:
    """LLM 结构化抽取甲乙方与金额。"""
    from app.rag.client import get_sf_client

    sf = get_sf_client()
    try:
        raw = sf.chat(messages=[{"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                                {"role": "user", "content": text[:6000]}],
                      model=settings.llm_chat_model, temperature=0, max_tokens=256)
        data = json.loads(raw)
        return {"party_a": data.get("party_a", ""), "party_b": data.get("party_b", ""), "amount": data.get("amount", "")}
    except Exception:  # noqa: BLE001
        return {"party_a": "", "party_b": "", "amount": ""}


# ===== 兼容层：保持旧接口（contracts.py 等调用方） =====
def parse_document(path: str, file_type: str) -> str:
    """解析文档为纯文本：file_type 可为 'pdf'/'docx'/'doc'/'txt'/'md'。"""
    suffix = file_type.lower().lstrip(".")
    return extract_text_from_file(path, suffix)


def extract_text_from_docx(path: str) -> str:
    return extract_text_from_file(path, "docx")


def extract_text_from_doc(path: str) -> str:
    return extract_text_from_file(path, "doc")


async def extract_contract_info(text: str) -> dict:
    """LLM 结构化抽取甲乙方与金额（async 包装）。"""
    return extract_contract_meta(text)


def _parse_json(raw: str) -> dict:
    import json
    import re

    m = re.search(r"\{[^{}]*\}", raw)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return {}


def _clean(val: str) -> str:
    return (val or "").strip()
