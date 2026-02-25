# -*- coding: utf-8 -*-
"""chunking.po - cutting text into meaningful pieces (chunks)."""

import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def chunk_document(doc_id, sections, head_meta=None):
    """
    Razbivaet dokument na chanki ~1000 simvolov s perekrytiem.
    """
    CHUNK_SIZE = 1000
    OVERLAP = 150
    
    all_chunks = []
    
    for sec in sections:
        text = sec.get("text", "")
        if not text:
            continue
            
        # Prostaya narezka (sliding window)
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            
            # We are trying to find the end of the sentence so as not to cut off the word in the middle
            # We are looking for a period, line feed or space at the end of the window
            window = text[start:end]
            
            # If this isn't the last piece
            if end < len(text):
                # We are looking for the last separator in the last quarter of the window
                last_space = -1
                for sep in [". ", "\n", " "]:
                    idx = window.rfind(sep, int(len(window)*0.75))
                    if idx != -1:
                        last_space = idx + len(sep) # Sdvigaem end srazu za razdelitel
                        break
                
                if last_space != -1:
                    end = start + last_space
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunk_meta = (head_meta or {}).copy()
                chunk_meta["chunk_start"] = start
                chunk_meta["chunk_len"] = len(chunk_text)
                
                all_chunks.append({
                    "text": chunk_text,
                    "meta": chunk_meta,
                    "doc_id": doc_id
                })
            
            start = end - OVERLAP
            # Protection from an eternal cycle if the overlap >= chunk_sitse (you never know)
            if start >= end:
                start = end
                
    return all_chunks