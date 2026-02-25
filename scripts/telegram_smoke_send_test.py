# -*- coding: utf-8 -*-
"""scripts/telegram_smoke_send_test.py

Otpravlyaet testovoe soobschenie adminu cherez Telegram Bot API.

Trebuetsya:
- TELEGRAM_BOT_TOKEN
- ADMIN_TG_ID

Zapusk (iz kornya proekta):
    python scripts/telegram_smoke_send_test.py

Zemnoy abzats:
Eto kak nazhat knopku "Test" na remote signalizatsii:
esli soobschenie doshlo do tebya v Telegram, provodka tselaya."""

from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("ADMIN_TG_ID", "").strip()

    if not token:
        print("[ERROR] TELEGRAM_BOT_TOKEN ne zadan.")
        return 1
    if not chat_id:
        print("[ERROR] ADMIN_TG_ID ne zadan.")
        return 1

    text = "Esther · Telegram stock test: connection works."

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
        }
    ).encode("utf-8")

    req = urllib.request.Request(api_url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            body = resp.read().decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        print(f"yuRRORshch Failed to complete the request to Telegram: ZZF0Z")
        return 1

    print("uINFOsch Telegram Reply:")
    print(body)

    # Normalizes the response and checks the flag ok=three
    normalized = body.replace(" ", "").replace("\n", "").lower()
    if '"ok":true' in normalized:
        print("YuOKshch Telegram confirms sending. Stoke send has passed.")
        return 0

    print('YuVARNsch There is no “ok” in the answer: three. Check the token and ADMIN_TG_ID manually.')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())