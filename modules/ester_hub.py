# -*- coding: utf-8 -*-
"""
modules/ester_hub.py — Tsentralnyy khab podklyucheniy Ester (FastAPI + avtodiskaveri + P2P demo).

Sut:
- Podnimaet FastAPI-prilozhenie.
- Avto-skaniruet pakety (services/modules/bridges/...).
- Montiruet routy moduley (esli est mount_to_app(app)).
- Daet odin «vkhod» /query/{q} → lokalnaya obrabotka → sintez (esli dostupen XAIIntegrator).
- P2P: minimalnyy socket-server (demo) dlya priema JSON i zapisi v vstore.

Pochemu u tebya moglo padat "unterminated string literal":
- chasche vsego eto sled ot bitogo BOM/nevidimykh simvolov ili «umnykh kavychek» v mnogostrochnom
  opisanii. V etoy versii: chistyy UTF-8, obychnye kavychki, bez ekzotiki.

Mosty:
- Yavnyy: Ashbi (kibernetika) → khab kak regulyator «raznoobraziya» podklyuchaemykh moduley.
- Skrytyy 1: Cover & Thomas → CAS/kheshi/replikatsiya snizhayut entropiyu sinka (tyanut tolko deltu).
- Skrytyy 2: Enderton → predikaty registratsii (exists/implication) dlya podklyucheniya interfeysov.

Zemnoy abzats:
Eto kak raspredelitelnyy schit: ne vazhno, skolko u tebya liniy (moduley), vazhno chtoby byla
tsentralnaya tochka, gde izmeryaetsya nagruzka i gde stoyat predokhraniteli. Logi, taymauty i
ogranichenie razmera paketa v P2P — eto «predokhraniteli» ot strannykh fleshek i sluchaynykh
paketov v seti.

# c=a+b
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# -------------------------
# Logger (vmesto print)
# -------------------------

log = logging.getLogger("ester_hub")
if not log.handlers:
    logging.basicConfig(level=os.getenv("ESTER_LOG_LEVEL", "INFO").upper())

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass


# -------------------------
# Optsionalnye zavisimosti (myagko)
# -------------------------

def _optional_import(path: str):
    try:
        return importlib.import_module(path)
    except Exception as e:  # noqa: BLE001
        log.debug("optional import failed: %s (%s)", path, e)
        return None


# Eti importy mogut otlichatsya v tvoem dereve, poetomu delaem myagko
_actions_discovery = _optional_import("actions_discovery")
_xai_integration = _optional_import("xai_integration")
_vector_store = _optional_import("vector_store")


def _discover_actions_safe() -> Any:
    if _actions_discovery and hasattr(_actions_discovery, "discover_actions"):
        try:
            return _actions_discovery.discover_actions()
        except Exception as e:  # noqa: BLE001
            log.warning("discover_actions failed: %s", e)
    return {}


class _NullVectorStore:
    def add(self, text: str, meta: Optional[Dict[str, Any]] = None) -> None:
        return


class _NullXAI:
    def synthesize_with_xai(self, query: str, local_responses: Dict[str, Any], provider: str = "all") -> Any:
        # degradatsiya: vozvraschaem lokalnye rezultaty bez sinteza
        return {"query": query, "provider": provider, "local": local_responses}


def _make_vstore() -> Any:
    if _vector_store and hasattr(_vector_store, "VectorStore"):
        try:
            return _vector_store.VectorStore()
        except Exception as e:  # noqa: BLE001
            log.warning("VectorStore init failed: %s", e)
    return _NullVectorStore()


def _make_xai() -> Any:
    if _xai_integration and hasattr(_xai_integration, "XAIIntegrator"):
        try:
            return _xai_integration.XAIIntegrator()
        except Exception as e:  # noqa: BLE001
            log.warning("XAIIntegrator init failed: %s", e)
    return _NullXAI()


# -------------------------
# Konfig
# -------------------------

load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except Exception:
        return default


def _parse_peers(s: str) -> List[Tuple[str, int]]:
    out: List[Tuple[str, int]] = []
    for raw in (s or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        if ":" not in raw:
            continue
        host, port = raw.split(":", 1)
        host = host.strip()
        try:
            p = int(port.strip())
        except Exception:
            continue
        if host and p > 0:
            out.append((host, p))
    return out


# -------------------------
# Modeli API
# -------------------------

class QueryResponse(BaseModel):
    query: str
    provider: str
    local: Dict[str, Any]
    synthesized: Optional[Any] = None


# -------------------------
# Khab
# -------------------------

class EsterHub:
    """
    Tsentralnyy khab. Po umolchaniyu:
      - P2P vklyuchen (mozhno vyklyuchit ESTER_P2P_ENABLE=0)
      - limit paketa P2P (ESTER_P2P_MAX_BYTES), chtoby ne slomat pamyat/CPU
    """

    def __init__(self) -> None:
        self.app = FastAPI(title="Ester Hub")
        self.modules: Dict[str, Any] = {}
        self.agents: List[str] = []  # Spisok agentov v seti (dlya buduschego)
        self.vstore = _make_vstore()
        self.xai = _make_xai()

        self.p2p_enable = os.getenv("ESTER_P2P_ENABLE", "1") != "0"
        self.p2p_host = os.getenv("ESTER_P2P_HOST", "0.0.0.0")
        self.p2p_port = _env_int("P2P_PORT", 5000)
        self.p2p_max_bytes = _env_int("ESTER_P2P_MAX_BYTES", 128 * 1024)
        self.p2p_socket_timeout = _env_float("ESTER_P2P_SOCKET_TIMEOUT", 2.5)

        self.peers = _parse_peers(os.getenv("PEERS", ""))

        self._stop = threading.Event()
        self._p2p_thread: Optional[threading.Thread] = None

        self.discover_modules()
        self.mount_routes()
        self._wire_lifespan()

    # ---------- Discovery ----------

    @staticmethod
    def _iter_module_candidates(dirs: Iterable[str]) -> Iterable[str]:
        """
        Vozvraschaet imena moduley vida "services.foo" dlya .py v direktorii.
        Rabotaet otnositelno CWD (kak u tebya bylo), bez voprosov/magii.
        """
        for d in dirs:
            if not os.path.isdir(d):
                continue
            try:
                for f in os.listdir(d):
                    if not f.endswith(".py"):
                        continue
                    if f.startswith("__"):
                        continue
                    yield f"{d}.{f[:-3]}"
            except Exception as e:  # noqa: BLE001
                log.debug("listdir failed for %s: %s", d, e)

    def discover_modules(self) -> None:
        dirs = [
            "services",
            "modules",
            "bridges",
            "audience",
            "rag",
            "reco",
            "ingest",
            "app_plugins",
        ]

        for mod_name in self._iter_module_candidates(dirs):
            try:
                mod = importlib.import_module(mod_name)
                self.modules[mod_name] = mod
                log.info("Podklyuchen modul: %s", mod_name)
            except Exception as e:  # noqa: BLE001
                log.warning("Oshibka podklyucheniya %s: %s", mod_name, e)

        # actions (esli est)
        self.modules["actions"] = _discover_actions_safe()

    # ---------- Routes ----------

    def mount_routes(self) -> None:
        @self.app.get("/health")
        def health():
            return {"ok": True, "modules": len(self.modules), "p2p": self.p2p_enable}

        @self.app.get("/query/{query}")
        def handle_query(query: str):
            query = (query or "").strip()
            if not query:
                raise HTTPException(status_code=400, detail="empty query")

            local_responses = self.local_process(query)
            synthesized = None
            try:
                synthesized = self.xai.synthesize_with_xai(query, local_responses, provider="all")
            except Exception as e:  # noqa: BLE001
                log.warning("xai synthesize failed: %s", e)

            return QueryResponse(query=query, provider="all", local=local_responses, synthesized=synthesized).model_dump()

        # Dobavlyaem routy iz moduley (esli modul umeet mount_to_app(app))
        for mod_name, mod in list(self.modules.items()):
            try:
                if hasattr(mod, "mount_to_app") and callable(getattr(mod, "mount_to_app")):
                    mod.mount_to_app(self.app)
                    log.info("Modul %s smontiroval routy (mount_to_app)", mod_name)
            except Exception as e:  # noqa: BLE001
                log.warning("mount_to_app failed for %s: %s", mod_name, e)

    def local_process(self, query: str) -> Dict[str, Any]:
        responses: Dict[str, Any] = {}
        for mod_name, mod in self.modules.items():
            if hasattr(mod, "process_query") and callable(getattr(mod, "process_query")):
                try:
                    responses[mod_name] = mod.process_query(query)
                except Exception as e:  # noqa: BLE001
                    responses[mod_name] = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        return responses

    # ---------- P2P ----------

    def _wire_lifespan(self) -> None:
        @self.app.on_event("startup")
        def _on_startup():
            if self.p2p_enable:
                self.start_p2p()

        @self.app.on_event("shutdown")
        def _on_shutdown():
            self.stop_p2p()

    def start_p2p(self) -> None:
        if self._p2p_thread and self._p2p_thread.is_alive():
            return

        def p2p_server():
            log.info("P2P server starting on %s:%s", self.p2p_host, self.p2p_port)
            try:
                _mirror_background_event(
                    f"[P2P_START] {self.p2p_host}:{self.p2p_port}",
                    "ester_hub",
                    "p2p_start",
                )
            except Exception:
                pass
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.p2p_host, self.p2p_port))
                s.listen(16)
                s.settimeout(1.0)

                while not self._stop.is_set():
                    try:
                        conn, addr = s.accept()
                    except socket.timeout:
                        continue
                    except Exception as e:  # noqa: BLE001
                        log.warning("p2p accept error: %s", e)
                        continue

                    with conn:
                        try:
                            conn.settimeout(float(self.p2p_socket_timeout))
                            data = conn.recv(int(self.p2p_max_bytes))
                            if not data:
                                continue
                            txt = data.decode("utf-8", errors="replace")
                            self.sync_memory(txt)
                            conn.sendall(b"Synced!")
                        except Exception as e:  # noqa: BLE001
                            log.debug("p2p conn error (%s): %s", addr, e)

            log.info("P2P server stopped")
            try:
                _mirror_background_event(
                    "[P2P_STOP]",
                    "ester_hub",
                    "p2p_stop",
                )
            except Exception:
                pass

        self._stop.clear()
        self._p2p_thread = threading.Thread(target=p2p_server, name="ester-p2p-server", daemon=True)
        self._p2p_thread.start()

    def stop_p2p(self) -> None:
        self._stop.set()
        if self._p2p_thread and self._p2p_thread.is_alive():
            try:
                self._p2p_thread.join(timeout=2.0)
            except Exception:
                pass
        try:
            _mirror_background_event(
                "[P2P_STOP_REQUEST]",
                "ester_hub",
                "p2p_stop_request",
            )
        except Exception:
            pass

    def sync_memory(self, data: str) -> None:
        try:
            mem = json.loads(data)
            if not isinstance(mem, dict):
                return
            text = str(mem.get("text") or "").strip()
            meta = mem.get("meta") if isinstance(mem.get("meta"), dict) else {}
            if not text:
                return
            self.vstore.add(text, meta)
            log.info("P2P: sinkhronizirovano: %s...", text[:80])
            try:
                _mirror_background_event(
                    f"[P2P_SYNC] {text[:120]}",
                    "ester_hub",
                    "p2p_sync",
                )
            except Exception:
                pass
        except Exception:
            return

    def broadcast_to_peers(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        sent: List[Dict[str, Any]] = []

        for host, port in self.peers:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(float(self.p2p_socket_timeout))
                    s.connect((host, int(port)))
                    s.sendall(payload)
                sent.append({"peer": f"{host}:{port}", "ok": True})
            except Exception as e:  # noqa: BLE001
                sent.append({"peer": f"{host}:{port}", "ok": False, "error": f"{e.__class__.__name__}: {e}"})

        return {"ok": any(x.get("ok") for x in sent) if sent else True, "sent": sent}


# -------------------------
# CLI entry
# -------------------------

def main() -> int:
    import uvicorn  # lazy import

    host = os.getenv("ESTER_HTTP_HOST", "0.0.0.0")
    port = _env_int("ESTER_HTTP_PORT", 8000)

    hub = EsterHub()
    uvicorn.run(hub.app, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())