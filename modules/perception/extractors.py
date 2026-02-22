# -*- coding: utf-8 -*-
import os
import mimetypes
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- DEPENDENCIES ---
try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx2txt
except ImportError:
    docx2txt = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

def extract_text(path: str) -> str:
    """
    Glavnaya tochka vkhoda. Opredelyaet tip fayla i vyzyvaet nuzhnyy rider.
    Vozvraschaet stroku s soderzhimym.
    """
    if not os.path.exists(path):
        return "[Error: File not found]"

    # Opredelyaem rasshirenie
    _, ext = os.path.splitext(path)
    ext = ext.lower()

    try:
        # === BOOKS & DOCS ===
        if ext == '.pdf':
            return _read_pdf(path)
        elif ext in ['.docx', '.doc']:
            return _read_docx(path)
        elif ext == '.fb2':
            return _read_fb2(path)
        
        # === IMAGES ===
        elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp']:
            return _read_image_ocr(path)
        
        # === CODE & TEXT ===
        elif ext in ['.txt', '.md', '.py', '.json', '.yaml', '.yml', '.log', '.csv', '.html', '.css', '.js', '.ini', '.env']:
            return _read_plain(path)
        
        else:
            # Fallback: probuem kak tekst
            return _read_plain(path)
    except Exception as e:
        return f"[Error extracting text from {os.path.basename(path)}: {str(e)}]"

def _read_plain(path: str) -> str:
    """Chitaet prostye tekstovye fayly."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        return f"[Error reading text: {e}]"

def _read_pdf(path: str) -> str:
    """Chitaet PDF cherez pypdf."""
    if not pypdf:
        return "[Error: Library 'pypdf' is missing. Run `pip install pypdf`]"
    
    text_content = []
    try:
        reader = pypdf.PdfReader(path)
        count = len(reader.pages)
        text_content.append(f"--- DOCUMENT: {os.path.basename(path)} ({count} pages) ---")
        
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_content.append(f"\n[PAGE {i+1}]\n{page_text}")
        
        return "\n".join(text_content)
    except Exception as e:
        return f"[PDF Error: {e}]"

def _read_docx(path: str) -> str:
    """Chitaet DOCX."""
    if not docx2txt:
        return "[Error: Library 'docx2txt' is missing. Run `pip install docx2txt`]"
    try:
        text = docx2txt.process(path)
        return f"--- DOCUMENT: {os.path.basename(path)} ---\n{text}"
    except Exception as e:
        return f"[DOCX Error: {e}]"

def _read_fb2(path: str) -> str:
    """Chitaet FB2 (XML) cherez BeautifulSoup."""
    if not BeautifulSoup:
        return "[Error: Library 'beautifulsoup4' is missing. Run `pip install beautifulsoup4 lxml`]"
    
    try:
        with open(path, 'rb') as f:
            content = f.read()
        
        # Parsim XML (lxml bystree i nadezhnee dlya FB2)
        soup = BeautifulSoup(content, 'xml')
        
        # Pytaemsya nayti metadannye
        title = "Unknown Title"
        t_tag = soup.find('book-title')
        if t_tag: title = t_tag.get_text(strip=True)
        
        # Telo knigi
        body = soup.find('body')
        if not body:
            # Esli body ne nashli, berem ves tekst
            text = soup.get_text(separator='\n', strip=True)
        else:
            # V FB2 struktura section -> p. Berem tekst s razdelitelyami.
            text = body.get_text(separator='\n\n', strip=True)
            
        return f"--- FB2 BOOK: {title} ---\n{text}"
    except Exception as e:
        # Fallback na prostoy tekst, esli XML bityy
        return f"[FB2 Parse Error: {e}]. Trying plain text...\n" + _read_plain(path)

def _read_image_ocr(path: str) -> str:
    """OCR izobrazheniy."""
    if not (Image and pytesseract):
        return "[Image received. OCR libraries missing.]"
    
    try:
        # Ukazhite put k tesseract, esli on ne v PATH
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        text = pytesseract.image_to_string(Image.open(path), lang='rus+eng')
        return f"--- IMAGE OCR: {os.path.basename(path)} ---\n{text}" if text.strip() else "[OCR: No text found]"
    except Exception as e:
        return f"[OCR Error: {e}]"