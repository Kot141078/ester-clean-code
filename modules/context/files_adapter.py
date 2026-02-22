# -*- coding: utf-8 -*-
"""
modules/context/files_adapter.py — adapter dlya prochitannykh faylov.

Posle uspeshnogo analiza ili chteniya fayla
vnosit zapis o soderzhimom v pamyat Ester.

# c=a+b
"""
from modules.context.adapters import log_context
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def record_file_read(filename: str, summary: str, meta: dict | None = None) -> None:
    meta = meta or {}
    meta.update({"filename": filename})
    text = f"Prochitan fayl {filename}: {summary}"
    log_context("file", "fact", text, meta)