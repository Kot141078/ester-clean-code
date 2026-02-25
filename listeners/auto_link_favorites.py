# -*- coding: utf-8 -*-
"""listeners/auto_link_favorites.py - avto-popolnenie "izbrannykh tseley" po katalogu uzlov.

Logika:
  • Periodicheski chitaem katalog uzlov (registry.node_catalog) i svoi nastroyki Telegram.
  • Esli u uzla sovpadaet PORTABLE_PROFILE (cap.env.portable_profile) i (po flagu) sovpadaet tg last_chat,
    addavlyaem (lan: node_id, tg: last_chat) v favorites.json.

ENV:
  AUTOLINK_POLL_SEC=20
  AUTOLINK_REQUIRE_TG_MATCH=1
  AUTOLINK_REQUIRE_PROFILE_MATCH=1

Mosty:
- Yavnyy (Svyaznost ↔ Planning): sozdaem ustoychivyy nabor predpochtitelnykh tseley.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): zanosim prichinu v meta.notes, fayl chitaem chelovekom.
- Skrytyy 2 (Praktika ↔ Sovmestimost): tolko stdlib; bez izmeneniy kontraktov ocheredi/registry.

Zemnoy abzats:
Kak na sklade: esli dva posta polzuyutsya odnim kanalom svyazi i odnim rezhimom - kladem ikh na polku “ryadom”.

# c=a+b"""
from __future__ import annotations
import argparse, json, os, time
from typing import Any, Dict

from modules.registry.node_catalog import list_nodes  # type: ignore
from modules.hybrid.favorites import add_favorite     # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _self_profile() -> str | None:
    try:
        from modules.registry.capabilities import build_capabilities  # type: ignore
        cap = build_capabilities()
        return ((cap.get("env") or {}).get("portable_profile"))
    except Exception:
        return os.getenv("PORTABLE_PROFILE")

def _self_tg_chat() -> int | None:
    try:
        from modules.telegram.settings import load_settings  # type: ignore
        cfg = load_settings()
        chat = (cfg.get("chats") or {}).get("last_chat")
        return int(chat) if chat else None
    except Exception:
        return None

def _match(cap: Dict[str, Any], me_prof: str | None, me_chat: int | None) -> bool:
    req_prof = os.getenv("AUTOLINK_REQUIRE_PROFILE_MATCH","1") == "1"
    req_tg   = os.getenv("AUTOLINK_REQUIRE_TG_MATCH","1") == "1"
    c_env = cap.get("env") or {}
    c_soc = cap.get("social") or {}
    c_tg  = (c_soc.get("tg") or {})
    cap_prof = c_env.get("portable_profile")
    cap_chat = c_tg.get("last_chat")
    if req_prof and (not me_prof or not cap_prof or me_prof != cap_prof):
        return False
    if req_tg and (not me_chat or not cap_chat or int(me_chat) != int(cap_chat)):
        return False
    return True

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester Auto-Link Favorites")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--period", type=int, default=int(os.getenv("AUTOLINK_POLL_SEC","20")))
    args = ap.parse_args(argv)

    try:
        while True:
            me_prof = _self_profile()
            me_chat = _self_tg_chat()
            try:
                xs = list_nodes().get("items") or []
            except Exception:
                xs = []
            for cap in xs:
                try:
                    if cap.get("schema") != "ester.cap/1": 
                        continue
                    node_id = cap.get("node_id")
                    if not node_id: 
                        continue
                    if not _match(cap, me_prof, me_chat):
                        continue
                    targets = {"lan":{"node": node_id}}
                    if me_chat: targets["tg"] = {"chat_id": me_chat}
                    add_favorite(targets, reason=f"auto-link: profile={me_prof}, tg_chat={me_chat}")
                except Exception:
                    continue
            print(json.dumps({"ts": int(time.time()), "mod":"autolink", "ab": AB, "prof": me_prof, "chat": me_chat}), flush=True)
            if not args.loop: break
            time.sleep(max(3, int(args.period)))
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b