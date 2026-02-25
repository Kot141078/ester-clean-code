# -*- coding: utf-8 -*-
from __future__ import annotations

"""config.py - configuratsiya Ester.

Fix pod error:
  cannot import name 'TZ' from 'config'

Nekotorye moduli (group_evening i pokhozhie) ozhidayut, chto v config.py est konstanta TZ.
V iskhodnike byl tolko cfg = EsterConfig(), bez TZ.

What was done:
- Added sovmestimost: TZ i helper get_timezone().
- Nothing ne lomaem: class EsterConfig i cfg ostayutsya kak byli.

Mosty:
- Yavnyy most: config TZ → planirovschiki (evening/group_digest) → predskazuemaya “fiziologiya” raspisaniy.
- Skrytyy most: kibernetika ↔ kod - backward-compat eksport snizhaet khrupkost avtoloaderov."""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


# --- Compatible for older modules ---
# Prioritet: ESTER_TZ → TZ → UTC
TZ = (os.getenv("ESTER_TZ") or os.getenv("TZ") or "UTC").strip() or "UTC"

# --- Legacy flat exports expected by tests and older modules ---
HOST = str(os.getenv("HOST") or "127.0.0.1")
PORT = _env_int("PORT", 5000)
DEBUG = _env_bool("DEBUG", False)
THREADED = _env_bool("THREADED", True)
CORS_ENABLED = _env_bool("CORS_ENABLED", False)
JWT_SECRET = str(os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY") or "")
PERSIST_DIR = str(os.getenv("PERSIST_DIR") or os.path.join(Path(__file__).resolve().parent, "data"))
COLLECTION_NAME = str(os.getenv("COLLECTION_NAME") or "ester_memory")
USE_EMBEDDINGS = _env_bool("USE_EMBEDDINGS", False)
EMBEDDINGS_API_BASE = str(os.getenv("EMBEDDINGS_API_BASE") or "http://127.0.0.1:1234/v1")
EMBEDDINGS_MODEL = str(os.getenv("EMBEDDINGS_MODEL") or "text-embedding-3-small")
OPENAI_API_KEY = str(os.getenv("OPENAI_API_KEY") or "")
USE_LOCAL_EMBEDDINGS = _env_bool("USE_LOCAL_EMBEDDINGS", True)
TZ_NAME = str(os.getenv("TZ_NAME") or TZ)


def get_timezone(default: str = "UTC") -> str:
    """Vernut stroku taymzony. Ne brosaet isklyucheniy."""
    v = (os.getenv("ESTER_TZ") or os.getenv("TZ") or TZ or default).strip()
    return v or default


class EsterConfig:
    def __init__(self):
        self.BASE_DIR = Path(__file__).resolve().parent
        self.CONFIG_PATH = os.path.join(self.BASE_DIR, "state", "runtime_config.json")

        # --- Bazovye konstanty (Hardcoded) ---
        self.ESTER_NAME = "Ester"
        self.CREATOR = "Owner"
        self.TIMEOUT = 3600

        # --- Puti ---
        self.PATHS = {
            "memory": os.path.join(self.BASE_DIR, "memory"),
            "logs": os.path.join(self.BASE_DIR, "logs"),
            "state": os.path.join(self.BASE_DIR, "state"),
        }

        # Initsializatsiya parametrov
        self.params = self._default_params()
        self.reload()

    def _default_params(self) -> dict:
        """Default settings if the Rintite_config.jsion file is missing."""
        return {
            "mode": "professional",  # professional / creative / observer
            "gpu_layers": int(os.getenv("GPU_LAYERS", 32)),
            "use_cloud_fallback": True,
            "active_modules": ["empathy_module", "topic_tracker", "idea", "rag_doc"],
        }

    def reload(self):
        """Loading dynamic settings from ZhSON."""
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.params.update(json.load(f))
            except Exception as e:
                logging.error(f"Error loading dynamic config: ЗЗФ0З")

    def save(self):
        """Saving current settings (for example, via a Telegram command)."""
        os.makedirs(os.path.dirname(self.CONFIG_PATH), exist_ok=True)
        with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.params, f, ensure_ascii=False, indent=2)

    @property
    def is_local_first(self) -> bool:
        return os.getenv("ESTER_HARDWARE") == "LOCAL"


# Sozdaem globalnyy obekt nastroek
cfg = EsterConfig()
