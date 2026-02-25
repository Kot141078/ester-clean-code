# -*- coding: utf-8 -*-
"""messaging.adapter.whatsapp_hsm - template messages (minimum).
# c=a+b"""
from __future__ import annotations
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
def send_template(phone: str, template: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"ok": True, "to": phone, "template": template, "params": params or {}}