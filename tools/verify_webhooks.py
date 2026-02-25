# -*- coding: utf-8 -*-
"""tools/verify_webhooks.py - CLI-verify configuratsii webhooks.

MOSTY:
- (Yavnyy) Pechataet podskazki URL/tokenov dlya Telegram/WhatsApp.
- (Skrytyy #1) Povtoryaet logiku /admin/webhooks/probe, no dlya terminala (CI/lokalno).
- (Skrytyy #2) Udobnyy odnorazovyy progon bez zapuska servera.

ZEMNOY ABZATs:
"Verified lampochki" do starta - vidno, where ne khvataet tokena/URL.

# c=a+b"""
from __future__ import annotations
import os, hmac, hashlib, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _h(key: str, msg: str) -> str:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

def main() -> int:
    base = os.getenv("TELEGRAM_BASE_URL", "http://127.0.0.1:8000")
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN","")
    tg_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET","")
    wa_token = os.getenv("WHATSAPP_ACCESS_TOKEN","")
    wa_pnid = os.getenv("WHATSAPP_PHONE_NUMBER_ID","")
    verify = os.getenv("WHATSAPP_VERIFY_TOKEN","")
    tg_url = f"{base.rstrip('/')}/telegram/webhook"
    wa_url = f"{os.getenv('WHATSAPP_GRAPH_BASE','https://graph.facebook.com/v20.0').rstrip('/')}/{wa_pnid}/messages"
    print("[telegram]")
    print("  webhook_url:", tg_url)
    print("  token_set:", bool(tg_token), "secret_set:", bool(tg_secret))
    print("  setWebhook:", f"curl -s -X POST 'https://api.telegram.org/bot{tg_token}/setWebhook' -d 'url={tg_url}?secret={tg_secret}'")
    print("[whatsapp]")
    print("  phone_number_id_set:", bool(wa_pnid), "access_token_set:", bool(wa_token), "verify_token_set:", bool(verify))
    print("  subscribe:", f"curl -s -X GET '{wa_url}?hub.mode=subscribe&hub.verify_token={verify}&hub.challenge=ping'")
    sample_sig = _h(os.getenv("P2P_HMAC_KEY","devkey"), "POST|/api/v2/synergy/assign|<ts>|<sha256(body)>")
    print("[p2p] sample hmac:", sample_sig)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b