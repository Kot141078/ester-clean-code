# -*- coding: utf-8 -*-
"""
scripts/telegram_smoke_env.py

Bystraya proverka Telegram-nastroek dlya Ester.

Proveryaet:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_WEBHOOK_SECRET / TELEGRAM_SECRET_TOKEN
- TELEGRAM_ALLOWED_UPDATES
- ADMIN_TG_ID

Osobennost:
- Pered proverkoy pytaetsya zagruzit peremennye iz .env v korne proekta,
  esli oni esche ne zadany v okruzhenii protsessa.
  Eto delaet vyvod skripta soglasovannym s tem, kak Ester chitaet konfig.

Zapusk (iz kornya proekta):
    python scripts/telegram_smoke_env.py

Zemnoy abzats:
Eto kak otkryt schitok i sverit, chto podpisannye avtomaty realno vklyucheny —
ne po pamyati, a po skheme v korobke (.env).
"""

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
    """
    Prosteyshiy zagruzchik .env bez vneshnikh zavisimostey.

    Logika:
    - esli peremennaya uzhe est v os.environ, NE pereopredelyaem;
    - podderzhivaem stroki vida KEY=VALUE;
    - ignoriruem kommentarii (#...) i pustye stroki;
    - probely vokrug imeni i znacheniya obrezaem;
    - kavychki vokrug VALUE snimaem, esli est.
    """
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

            # Esli uzhe zadano v okruzhenii — ne trogaem (prioritet u vneshney sredy)
            if name in os.environ:
                continue

            value = value.strip()
            # Snimaem odinarnye/dvoynye kavychki po krayam, esli est
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

            os.environ[name] = value
    except Exception as e:  # noqa: BLE001
        # Ne valim smoke, prosto preduprezhdaem.
        print(f"[WARN] Ne udalos korrektno prochitat .env: {e}")


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
    # Podkhvatyvaem .env iz kornya proekta (esli est)
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
                "(obychno soderzhit dvoetochie i dostatochno dlinnyy)."
            )
    else:
        _warn(
            "TELEGRAM_BOT_TOKEN ne zadan. Bez nego bot ne smozhet otpravlyat "
            "soobscheniya i prinimat webhook."
        )

    if secret:
        if len(secret) >= 10:
            _ok("Webhook secret (TELEGRAM_WEBHOOK_SECRET/TELEGRAM_SECRET_TOKEN) zadan.")
        else:
            _warn("Webhook secret zadan, no vyglyadit korotkim — luchshe >=10 simvolov.")
    else:
        _warn(
            "Webhook secret ne zadan. Webhook budet rabotat, no bez proverki "
            "X-Telegram-Bot-Api-Secret-Token."
        )

    if allowed:
        parsed = None
        try:
            parsed = json.loads(allowed)
            if isinstance(parsed, list):
                _ok(f"TELEGRAM_ALLOWED_UPDATES kak JSON: {parsed}")
            else:
                _warn(
                    "TELEGRAM_ALLOWED_UPDATES kak JSON ne yavlyaetsya spiskom, "
                    "probuem interpretirovat kak CSV."
                )
                parsed = None
        except Exception:
            parsed = None

        if parsed is None:
            parts = [p.strip() for p in allowed.split(",") if p.strip()]
            if parts:
                _ok(f"TELEGRAM_ALLOWED_UPDATES kak spisok: {parts}")
            else:
                _warn(
                    "TELEGRAM_ALLOWED_UPDATES zadan, no format ne razobran. "
                    "Ostavlyaem kak est."
                )
    else:
        _warn(
            "TELEGRAM_ALLOWED_UPDATES ne zadan. Budut prinimatsya standartnye tipy "
            "apdeytov Telegram."
        )

    if admin:
        if admin.isdigit():
            _ok(f"ADMIN_TG_ID={admin} — OK (vyglyadit kak chislovoy chat id).")
        else:
            _warn(
                "ADMIN_TG_ID zadan, no ne yavlyaetsya chislom. Obychno eto numeric chat id."
            )
    else:
        _warn("ADMIN_TG_ID ne zadan. Smoke-test otpravki soobscheniya rabotat ne budet.")

    if not token and not admin:
        _err(
            "Net TELEGRAM_BOT_TOKEN i ADMIN_TG_ID — Telegram-integratsiya fakticheski "
            "vyklyuchena."
        )
        exit_code = 1

    print("[SMOKE] telegram_smoke_env zavershen.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())