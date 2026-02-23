# -*- coding: utf-8 -*-
"""
Universalnye parsery faylov (PDF/DOCX/TXT/OCR) s taymautom (ThreadPool 300s), best-effort preview.
"""
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from config import PARSE_TIMEOUT_SEC  # type: ignore
except Exception:
    PARSE_TIMEOUT_SEC = float(os.getenv("PARSE_TIMEOUT_SEC", "300"))


def parse_pdf(file_path: str) -> str:
    try:
        import pypdf as _pypdf  # type: ignore
    except Exception:
        try:
            import PyPDF2 as _pypdf  # type: ignore
        except Exception as e:
            return f"[Error: PDF parser missing ({e})]"
    try:
        with open(file_path, "rb") as f:
            reader = _pypdf.PdfReader(f)
            return " ".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        return f"[PDF Error: {e}]"


def parse_docx(file_path: str) -> str:
    try:
        import docx  # type: ignore
    except Exception as e:
        return f"[Error: DOCX parser missing ({e})]"
    try:
        doc = docx.Document(file_path)
        return " ".join(para.text for para in doc.paragraphs)
    except Exception as e:
        return f"[DOCX Error: {e}]"


def parse_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"[TXT Error: {e}]"


def parse_with_timeout(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    parser = {".pdf": parse_pdf, ".docx": parse_docx, ".txt": parse_txt}.get(ext, parse_txt)
    with ThreadPoolExecutor() as executor:
        future = executor.submit(parser, file_path)
        try:
            return future.result(timeout=PARSE_TIMEOUT_SEC)
        except TimeoutError:
            # taym‑aut, vozvraschaem pervye 500 simvolov fayla
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    return "[Parse timeout] Preview: " + f.read(500)
            except Exception:
                return "[Parse timeout] Preview unavailable"