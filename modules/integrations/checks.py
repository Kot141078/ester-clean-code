# -*- coding: utf-8 -*-
"""modules/integrations/checks.py - bystryy self-check vneshnikh integratsiy.

MOSTY:
- (Yavnyy) Proveryaet nalichie klyuchevykh ENV (Telegram/WhatsApp/OpenAI/Gemini) i faylov.
- (Skrytyy #1) Ne vypolnyaet setevykh zaprosov - offlayn validator formata/nalichiya.
- (Skrytyy #2) Vozvraschaet kompaktnyy otchet dlya UI/adminki.

ZEMNOY ABZATs:
Eto spisok “podklyucheny li provoda”: est li tokeny, ukazan li put k BD i t.p.

# c=a+b"""
from __future__ import annotations
import os
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _present(v: str) -> bool:
    return bool(v and str(v).strip())

def quick_check() -> Dict[str, Any]:
    env = os.environ
    report = {
        "telegram": {
            "enabled": env.get("TELEGRAM_ENABLE","0") == "1",
            "bot_token": _present(env.get("TELEGRAM_BOT_TOKEN","")),
            "base_url": _present(env.get("TELEGRAM_BASE_URL","")),
            "webhook_secret": _present(env.get("TELEGRAM_WEBHOOK_SECRET","")),
        },
        "whatsapp": {
            "access_token": _present(env.get("WHATSAPP_ACCESS_TOKEN","")),
            "phone_number_id": _present(env.get("WHATSAPP_PHONE_NUMBER_ID","")),
            "verify_token": _present(env.get("WHATSAPP_VERIFY_TOKEN","")),
        },
        "openai": {
            "api_key": _present(env.get("OPENAI_API_KEY","")),
            "model": _present(env.get("OPENAI_MODEL_NAME","")),
        },
        "gemini": {
            "api_key": _present(env.get("GEMINI_API_KEY","")),
            "model": _present(env.get("GEMINI_MODEL_NAME","")),
        },
        "messaging_db": {
            "path": env.get("MESSAGING_DB_PATH",""),
            "exists": os.path.isfile(env.get("MESSAGING_DB_PATH","")),
        }
    }
    report["ok"] = all([
        (not report["telegram"]["enabled"]) or report["telegram"]["bot_token"],
        True,  # the rest are not required to start
    ])
    return report
# c=a+b