# -*- coding: utf-8 -*-
"""scripts/telegram_smoke_webhook.py

Verka dostupnosti Telegram webhook v Ester.

Delaet:
1) GET /api/telegram/webhook - ping.
2) POST /api/telegram/webhook s testovym apdeytom:
   - s X-Telegram-Bot-Api-Secret-Token, esli TELEGRAM_WEBHOOK_SECRET/TELEGRAM_SECRET_TOKEN zadan.

Route:
- Use /api/telegram/webhook iz routes/telegram_webhook_routes.py.
- Bazovyy URL mozhno pereopredelit argumentom ili ENV ESTER_WEBHOOK_BASE_URL.

Zapusk (iz kornya proekta):
    python scripts/telegram_smoke_webhook.py
    python scripts/telegram_smoke_webhook.py http://localhost:8000"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _base_url_from_env() -> str | None:
    v = os.getenv("ESTER_WEBHOOK_BASE_URL", "").strip()
    return v or None


def _norm_base(url: str) -> str:
    return url.rstrip("/")


def _http_get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5.0) as r:
            return r.getcode(), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def _http_post(url: str, data: dict, headers: dict[str, str] | None = None) -> tuple[int, str]:
    body = json.dumps(data).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5.0) as r:
            return r.getcode(), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def main() -> int:
    # Bazovyy URL: argument CLI > ENV > defolt
    base = None
    if len(sys.argv) > 1:
        base = sys.argv[1].strip()
    if not base:
        base = _base_url_from_env()
    if not base:
        # typical option for local Flask
        base = "http://localhost:8000"
    base = _norm_base(base)

    secret = (
        os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
        or os.getenv("TELEGRAM_SECRET_TOKEN", "").strip()
    )

    ping_url = f"{base}/api/telegram/webhook"
    print(f"[INFO] GET {ping_url}")
    code, body = _http_get(ping_url)
    if code == 200:
        print("[OK] /api/telegram/webhook otvechaet 200.")
    else:
        print(f"[WARN] /api/telegram/webhook vernul kod {code}. Telo: {body}")
        # It does not crash immediately: perhaps the route is different or has not yet been installed.

    # Gotovim testovyy apdeyt
    fake_update = {
        "update_id": 999999999,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 0, "type": "private"},
            "text": "telegram_smoke_webhook",
        },
    }

    headers = {}
    if secret:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret
        print("uINFOsch We use the secret for the header S-Telegram-Here-Api-Secret-Token.")

    post_url = f"{base}/api/telegram/webhook"
    print(f"[INFO] POST {post_url} (test update)")
    code, body = _http_post(post_url, fake_update, headers=headers)

    if code == 200:
        print("[OK] Webhook prinyal testovyy apdeyt (200).")
        print("ySMOKESh telegram_stock_webhook completed successfully.")
        return 0

    print(f"YuVARNsch Webhook responded with the code ZZF0Z. Tel: ZZF1ZZ")
    print("YuVARNsch Check the route /api/telegram/webhook and secret.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())