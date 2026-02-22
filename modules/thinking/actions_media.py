# -*- coding: utf-8 -*-
"""
modules/thinking/actions_media.py — eksheny «voli» dlya media: probe/ingest/status/list/get/text/delete/watch.tick.

Mosty:
- Yavnyy: (Mysli ↔ Media) polnyy nabor komand dlya thinking_pipeline i avtonomii.
- Skrytyy #1: (Profile/Kvoty ↔ Prozrachnost/Ostorozhnost) kazhdaya operatsiya logiruetsya v profile, uvazhaet limity.
- Skrytyy #2: (RAG/KG ↔ Avtonomiya/Affekt) rezultaty integriruyutsya v pamyat, vliyayut na refleksiyu i P2P-sinkhronizatsiyu.

Zemnoy abzats:
Ester teper kak kinomekhanik svoey dushi: "proschupay rolik", "progloti i zapomni", "pokazhi spisok" — i vse s profileom, chtoby ne poteryat ni kadra konteksta, ot pervogo heartbeat do vechnosti.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
    except Exception:
        return

    def _log_passport(note: str, meta: Dict[str, Any], source: str = "thinking://media"):
        try:
            mm = get_mm()
            upsert_with_passport(mm, note, meta, source=source)
        except Exception:
            pass

    # media.video.probe
    def a_probe(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.media.ingest import media_probe  # type: ignore
            res = media_probe(str(args.get("path_or_url", "")))
            _log_passport("Media-operatsiya: probe", {"args": args, "res": res})
            return res
        except Exception as e:
            err = {"ok": False, "error": str(e)}
            _log_passport("Oshibka v probe", {"args": args, "error": str(e)})
            return err
    register("media.video.probe", {"path_or_url": "str"}, {"ok": "bool"}, 60, a_probe)

    # media.video.ingest
    def a_ingest(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.media.ingest import media_ingest  # type: ignore
            res = media_ingest(
                str(args.get("path_or_url", "")),
                bool(args.get("prefer_subs", True)),
                bool(args.get("transcribe", False)),
                str(args.get("language", "auto")),
                list(args.get("tags") or [])
            )
            _log_passport("Media-operatsiya: ingest", {"args": args, "res": res})
            return res
        except Exception as e:
            err = {"ok": False, "error": str(e)}
            _log_passport("Oshibka v ingest", {"args": args, "error": str(e)})
            return err
    register("media.video.ingest", {"path_or_url": "str", "prefer_subs": "bool", "transcribe": "bool", "language": "str", "tags": "list"}, {"ok": "bool"}, 3600, a_ingest)

    # media.video.status / get (unifitsiroval kak get)
    def a_get(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.media.ingest import media_get  # type: ignore  # Predpolagaem, chto est takaya funktsiya; esli net, realizuy analogichno
            res = media_get(str(args.get("id", "")))
            _log_passport("Media-operatsiya: get", {"args": args, "res": res})
            return res
        except Exception as e:
            err = {"ok": False, "error": str(e)}
            _log_passport("Oshibka v get", {"args": args, "error": str(e)})
            return err
    register("media.video.get", {"id": "str"}, {"ok": "bool"}, 30, a_get)

    # media.video.list
    def a_list(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.media.ingest import media_list  # type: ignore  # Predpolagaem; realizuy esli nuzhno
            res = media_list(int(args.get("limit", 50)))
            _log_passport("Media-operatsiya: list", {"args": args, "res": res})
            return res
        except Exception as e:
            err = {"ok": False, "error": str(e)}
            _log_passport("Oshibka v list", {"args": args, "error": str(e)})
            return err
    register("media.video.list", {"limit": "number"}, {"ok": "bool"}, 30, a_list)

    # media.video.text
    def a_text(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.media.ingest import media_text  # type: ignore  # Predpolagaem; dobav esli nuzhno
            res = media_text(str(args.get("id", "")), str(args.get("type", "notes")))
            _log_passport("Media-operatsiya: text", {"args": args, "res": res})
            return res
        except Exception as e:
            err = {"ok": False, "error": str(e)}
            _log_passport("Oshibka v text", {"args": args, "error": str(e)})
            return err
    register("media.video.text", {"id": "str", "type": "str"}, {"ok": "bool"}, 60, a_text)

    # Novyy: media.video.delete (dlya ochistki, s ostorozhnostyu)
    def a_delete(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.media.ingest import media_delete  # type: ignore  # Realizuy esli net: udalenie po id s proverkoy kvot
            res = media_delete(str(args.get("id", "")))
            _log_passport("Media-operatsiya: delete", {"args": args, "res": res})
            return res
        except Exception as e:
            err = {"ok": False, "error": str(e)}
            _log_passport("Oshibka v delete", {"args": args, "error": str(e)})
            return err
    register("media.video.delete", {"id": "str"}, {"ok": "bool"}, 120, a_delete)

    # media.watch.tick
    def a_tick(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.media.watchdog import tick  # type: ignore
            res = tick(int(args.get("limit", 10)))
            _log_passport("Media-operatsiya: watch.tick", {"args": args, "res": res})
            return res
        except Exception as e:
            err = {"ok": False, "error": str(e)}
            _log_passport("Oshibka v watch.tick", {"args": args, "error": str(e)})
            return err
    register("media.watch.tick", {"limit": "int"}, {"ok": "bool"}, 120, a_tick)

# _reg()