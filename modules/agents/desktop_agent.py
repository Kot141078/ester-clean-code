# -*- coding: utf-8 -*-
"""
modules/agents/desktop_agent.py — rasshirenie M27: operatsiya click_text.

Novaya operatsiya (kind):
  - click_text  meta: {"text":"OK","image_path?":"/tmp/ester_screenshot.png"}

Plan: [{"do":"capture"},{"do":"ocr_find","text":"..."},{"do":"click","x":"{{OCR_X}}","y":"{{OCR_Y}}"}]
V realnom vypolnenii koordinaty podstavlyayutsya posle dry-run cherez DesktopVision++.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from modules.agents.base_agent import AgentBase, Action
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class DesktopAgent(AgentBase):
    def __init__(self):
        super().__init__("desktop")

    def plan(self, a:Action):
        k=a.kind; m=a.meta or {}
        plan=[]
        if k=="open_app":
            plan=[{"do":"launch", "app": m.get("app","notepad"), "args": m.get("args",[])}]
        elif k=="type_text":
            plan=[{"do":"focus","target":m.get("target","active_window")},
                  {"do":"type","text": m.get("text","")}]
        elif k=="open_url":
            plan=[{"do":"launch","app": m.get("browser","system")},
                  {"do":"navigate","url": m.get("url","https://example.org")}]
        elif k=="focus_app":
            plan=[{"do":"focus","app": m.get("app","")}]
        elif k=="screenshot":
            plan=[{"do":"capture","target":"screen"}]
        elif k=="click_anchor":
            anc=m.get("anchor","")
            img=m.get("image_path","/tmp/ester_screenshot.png")
            plan=[{"do":"capture","target":"screen","path":img},
                  {"do":"find","anchor":anc,"path":img},
                  {"do":"click","x":"{{VISION_X}}","y":"{{VISION_Y}}"}]
        elif k=="click_text":
            key=m.get("text","")
            img=m.get("image_path","/tmp/ester_screenshot.png")
            plan=[{"do":"capture","target":"screen","path":img},
                  {"do":"ocr_find","text":key,"path":img},
                  {"do":"click","x":"{{OCR_X}}","y":"{{OCR_Y}}"}]
        else:
            plan=[{"do":"noop","msg":"unknown kind"}]
        return plan, {"note":"desktop plan"}