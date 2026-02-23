# check_env.py
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = Path(__file__).resolve().parent
env_path = ROOT / ".env"
loaded = load_dotenv(env_path)


def mask(val: str | None, keep: int = 4) -> str | None:
    if not val:
        return None
    if len(val) <= keep * 2:
        return val[0:1] + "…" if len(val) > 1 else "…"
    return val[:keep] + "…" + val[-keep:]


print(f"cwd={ROOT}")
print(f".env path={env_path} exists={env_path.exists()} loaded={loaded}")

keys = [
    "HOST",
    "PORT",
    "DEBUG",
    "THREADED",
    "LOG_LEVEL",
    "PRIMARY_PROVIDER",
    "DEFAULT_CHAT_PROVIDER",
    "LM_STUDIO_API_URL",
    "LM_STUDIO_MODEL",
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "MEMORY_NAMESPACE_UUID",
]
for k in keys:
    v = os.getenv(k)
    if k.endswith("_KEY") or "TOKEN" in k:
        v = mask(v)
    print(f"{k} = {v}")

ok = True
tt = os.getenv("TELEGRAM_TOKEN")
if not tt:
    print("WARN: TELEGRAM_TOKEN is empty -> Telegram bot will be disabled")
    ok = False

uuid = os.getenv("MEMORY_NAMESPACE_UUID")
if uuid and any(ch for ch in uuid if ch.lower() not in "0123456789abcdef-"):
    print(
        "WARN: MEMORY_NAMESPACE_UUID contains non-hex characters; regenerate (only 0-9,a-f and dashes)."
    )
    ok = False

# sys.exit(0 if ok else 1)