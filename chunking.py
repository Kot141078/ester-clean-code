# -*- coding: utf-8 -*-
"""
chunking.py — narezka teksta na smyslovye kuski (chanki).
"""

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
            
            # Pytaemsya nayti konets predlozheniya, chtoby ne rezat poseredine slova
            # Ischem tochku, perevod stroki ili probel v kontse okna
            window = text[start:end]
            
            # Esli eto ne posledniy kusok
            if end < len(text):
                # Ischem posledniy razdelitel v posledney chetverti okna
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
            # Zaschita ot vechnogo tsikla, esli overlap >= chunk_size (malo li)
            if start >= end:
                start = end
                
    return all_chunks