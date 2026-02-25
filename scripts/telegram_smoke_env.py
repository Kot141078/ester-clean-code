# -*- coding: utf-8 -*-
"""scripts/telegram_smoke_env.py

Bystraya proverka Telegram-nastroek dlya Ester.

Proveryaet:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_WEBHOOK_SECRET / TELEGRAM_SECRET_TOKEN
- TELEGRAM_ALLOWED_UPDATES
- ADMIN_TG_ID

Features:
- Pered proverkoy pytaetsya zagruzit peremennye iz .env v korne proekta,
  esli oni esche ne zadany v okruzhenii protsessa.
  Eto delaet vyvod skripta soglasovannym s tem, kak Ester chitaet konfig.

Zapusk (iz kornya proekta):
    python scripts/telegram_smoke_env.py

Zemnoy abzats:
Eto kak otkryt schitok i sverit, chto podpisannye avtomaty realno vklyucheny —
ne po pamyati, a po scheme v korobke (.env)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env_from_file(path: Path) -> None:
    """Prosteyshiy zagruzchik .env bez vneshnikh zavisimostey.

    Logika:
    - esli peremennaya uzhe est v os.environ, NE pereopredelyaem;
    - podderzhivaem stroki vida KEY=VALUE;
    - ignore comments (#...) i empty lines;
    - probely vokrug imeni i znacheniya obrezaem;
    - kavychki vokrug VALUE snimaem, esli est."""
    if not path.is_file():
        return

    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if not name or name.startswith("#"):
                continue

            # If it is already set in the environment, do not touch it (priority is with the external environment)
            if name in os.environ:
                continue

            value = value.strip()
            # Remove single/double quotes around the edges, if any
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

            os.environ[name] = value
    except Exception as e:  # noqa: BLE001
        # We're not throwing down the drain, we're just warning you.
        print(f"YuVARNsch Could not read correctly .env: ZZF0Z")


def _get(name: str) -> str | None:
    v = os.getenv(name, "").strip()
    return v or None


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _err(msg: str) -> None:
    print(f"[ERROR] {msg}")


def main() -> int:
    # Picks up .env from the project root (if any)
    _load_env_from_file(ROOT / ".env")

    token = _get("TELEGRAM_BOT_TOKEN")
    secret = _get("TELEGRAM_WEBHOOK_SECRET") or _get("TELEGRAM_SECRET_TOKEN")
    allowed = _get("TELEGRAM_ALLOWED_UPDATES")
    admin = _get("ADMIN_TG_ID")

    exit_code = 0

    if token:
        if ":" in token and len(token) > 30:
            _ok("TELEGRAM_BOT_TOKEN vyglyadit pravdopodobno.")
        else:
            _warn(
                "TELEGRAM_BOT_TOKEN zadan, no format podozritelnyy "
                "(usually contains a colon and is quite long)."
            )
    else:
        _warn(
            "TELEGRAM_HERE_TOKEN is not specified. Without it, the bot will not be able to send"
            "messages and receive webhook."
        )

    if secret:
        if len(secret) >= 10:
            _ok("Webhook secret (TELEGRAM_WEBHOOK_SECRET/TELEGRAM_SECRET_TOKEN) zadan.")
        else:
            _warn("The webhook secret is set, but it looks short - better >=10 characters.")
    else:
        _warn(
            "Webhook secret not set. Webhook will work, but without checking"
            "X-Telegram-Bot-Api-Secret-Token."
        )

    if allowed:
        parsed = None
        try:
            parsed = json.loads(allowed)
            if isinstance(parsed, list):
                _ok(f"TELEGRAM_ALLOWED_UPDATES as JSON: {parsed}")
            else:
                _warn(
                    "TELEGRAM_ALLOVED_UPDATES as ZhSION is not a list,"
                    "we try to interpret it as CSV."
                )
                parsed = None
        except Exception:
            parsed = None

        if parsed is None:
            parts = [p.strip() for p in allowed.split(",") if p.strip()]
            if parts:
                _ok(f"TELEGRAM_ALLOVED_UPDATES as list: ZZF0Z")
            else:
                _warn(
                    "TELEGRAM_ALLOWED_UPDATES zadan, no format ne razobran. "
                    "Let's leave it as is."
                )
    else:
        _warn(
            "TELEGRAM_ALLOWED_UPDATES ne zadan. Budut prinimatsya standartnye tipy "
            "apdeytov Telegram."
        )

    if admin:
        if admin.isdigit():
            _ok(f"ADMIN_TG_ID=ZZF0Z - OK (looks like a numeric chat ID).")
        else:
            _warn(
                "ADMIN_TG_ID is specified, but is not a number. Usually this is numeric chat id."
            )
    else:
        _warn("ADMIN_TG_ID is not specified. The stock test of sending a message will not work.")

    if not token and not admin:
        _err(
            "No TELEGRAM_HERE_TOKEN and ADMIN_TG_ID - Telegram integration actually"
            "vyklyuchena."
        )
        exit_code = 1

    print("[SMOKE] telegram_smoke_env zavershen.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())