# -*- coding: utf-8 -*-
"""
bin/messaging_webhooks.py — CLI dlya upravleniya Telegram webhook (set/delete).

MOSTY:
- (Yavnyy) Pryamye vyzovy Telegram Bot API: setWebhook/deleteWebhook s optional secret_token.
- (Skrytyy #1) Dry-run rezhim po umolchaniyu pri otsutstvii TELEGRAM_BOT_TOKEN — pechataet curl/URL, no ne vyzyvaet set.
- (Skrytyy #2) Validatsiya URL i zagolovkov, akkuratnye kody vykhoda.

ZEMNOY ABZATs:
Odin instrument dlya bezopasnoy ustanovki vebkhuka v TG. Dlya WhatsApp vebkhuk zadaetsya v Meta App → Webhooks (UI),
poetomu zdes vyvodyatsya podskazki/proverki, a ne pryamye vyzovy Graph API.

# c=a+b
"""
from __future__ import annotations
import os, sys, json, argparse, urllib.parse, urllib.request

try:
    from modules.security.net_guard import deny_payload, is_outbound_network_allowed
except Exception:
    def is_outbound_network_allowed() -> bool:  # type: ignore
        return False

    def deny_payload(target: str = "outbound_network") -> dict:  # type: ignore
        return {
            "ok": False,
            "error": "network_denied",
            "target": target,
            "reason": "closed_box_default_deny",
            "hint": "Set ESTER_ALLOW_OUTBOUND_NETWORK=1 to allow outbound network.",
        }

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def _is_url(x: str) -> bool:
    try:
        u = urllib.parse.urlparse(x)
        return u.scheme in ("http", "https") and bool(u.netloc)
    except Exception:
        return False

def tg_set(url: str, secret: str | None, dry: bool) -> int:
    if not _is_url(url):
        print("error: invalid url", file=sys.stderr); return 2
    if dry or not TG_TOKEN:
        curl = f'curl -s "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url={urllib.parse.quote(url)}' + (f'&secret_token={secret}"' if secret else '"')
        print("# dry-run (no TELEGRAM_BOT_TOKEN)\n", curl)
        return 0
    if not is_outbound_network_allowed():
        print(json.dumps(deny_payload("telegram_webhook"), ensure_ascii=True))
        return 3
    api = f"https://api.telegram.org/bot{TG_TOKEN}/setWebhook"
    qs = {"url": url}
    if secret: qs["secret_token"] = secret
    data = urllib.parse.urlencode(qs).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(api, data=data, method="POST"), timeout=6.0) as r:
        print(r.read().decode("utf-8", "ignore"))
    return 0

def tg_delete(dry: bool) -> int:
    if dry or not TG_TOKEN:
        print('# dry-run (no TELEGRAM_BOT_TOKEN)\ncurl -s "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook"')
        return 0
    if not is_outbound_network_allowed():
        print(json.dumps(deny_payload("telegram_webhook"), ensure_ascii=True))
        return 3
    api = f"https://api.telegram.org/bot{TG_TOKEN}/deleteWebhook"
    with urllib.request.urlopen(urllib.request.Request(api, method="POST"), timeout=6.0) as r:
        print(r.read().decode("utf-8", "ignore"))
    return 0

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="messaging_webhooks", description="Ester messaging webhooks CLI")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--tg-set", metavar="URL", help="Set Telegram webhook to URL")
    g.add_argument("--tg-delete", action="store_true", help="Delete Telegram webhook")
    p.add_argument("--secret", help="Telegram secret_token for webhook")
    p.add_argument("--dry", action="store_true", help="Dry run (print commands only)")
    a = p.parse_args(argv)

    if a.tg_set:
        return tg_set(a.tg_set, a.secret, a.dry)
    if a.tg_delete:
        return tg_delete(a.dry)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
