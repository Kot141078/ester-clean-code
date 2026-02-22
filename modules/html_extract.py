# -*- coding: utf-8 -*-
"""
modules/html_extract.py - Extracts clean text from raw HTML.
Dependency: pip install beautifulsoup4 requests
"""
import requests
from bs4 import BeautifulSoup
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def fetch_and_clean(url):
    """Downloads URL, strips boilerplates, returns clean text."""
    try:
        headers = {"User-Agent": "Ester/1.0 (SovereignNode)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Kill all script and style elements
        for script in soup(["script", "style", "nav", "footer", "iframe"]):
            script.decompose()
            
        text = soup.get_text(separator="\n")
        
        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = "\n".join(chunk for chunk in chunks if chunk)
        
        return {"ok": True, "text": text, "title": soup.title.string if soup.title else url}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}