# -*- coding: utf-8 -*-
"""modules/thinking/actions_social.py - eksheny “voli” dlya kampaniy/kitov/ledzhera, s aploadom i monitoringom.

Mosty:
- Yavnyy: (Mysli ↔ Sotsdeploy) daet korotkie komandy dlya planirovaniya, sborki, aploada i zhurnala.
- Skrytyy #1: (Avtonomiya ↔ Volya) mozhno zapuskat na sobytiya (gotovo video → sobrat kit → upload).
- Skrytyy #2: (Finansy ↔ Otchet) fiksiruem metriki v ledzhere dlya posleduyuschikh resheniy.
- Skrytyy #3: (P2P ↔ Raspredelenie) posle uspekha sinkhroniziruem metriki v detsentralizovannuyu BZ.

Zemnoy abzats:
Mozg govorit: “zaplaniruy kampaniyu”, “soberi kit”, “opublikuy”, “zapishi prosmotry”, “pokazhi status” - i Ester obsluzhivaet ves tsikl, s yumorom: 'Ya v sotssetyakh - zvezda!'.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
import json, os, time, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _passport(note: str, meta: dict) -> None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        upsert_with_passport(mm, note, meta, source="thinking://actions_social")
        # P2P synchronization: Here you can add metadata distribution across a network of agents
        # Naprimer: _p2p_sync(meta, nodes=["node1:port", "node2:port"])
    except Exception:
        pass  # Esther is silent about mistakes, but remember

def _p2p_sync(meta: dict, nodes: list[str]) -> None:
    # Offline cue: record sync intent without network calls.
    queue_path = os.getenv("SOCIAL_P2P_SYNC_QUEUE", "data/social/p2p_sync_queue.jsonl")
    os.makedirs(os.path.dirname(queue_path) or ".", exist_ok=True)
    safe_nodes = [str(n).strip() for n in (nodes or []) if str(n).strip()][:16]
    payload = meta if isinstance(meta, dict) else {"value": str(meta)}
    rec = {"ts": int(time.time()), "nodes": safe_nodes, "meta": payload, "mode": "offline_queue"}
    with open(queue_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_plan(args: Dict[str, Any]):
        try:
            from modules.social.campaign import plan
            result = plan(str(args.get("id", "")), dict(args.get("sources") or {}), list(args.get("platforms") or []), list(args.get("tags") or []))
            _passport("social.campaign.plan", {"ok": result.get("ok", False), "id": args.get("id")})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    register("social.campaign.plan", {"id": "str"}, {"ok": "bool"}, 6, a_plan)

    def a_build(args: Dict[str, Any]):
        try:
            mode = str(args.get("mode", "auto")).lower()  # auto: probuet rest, fallback local
            platform = str(args.get("platform", "tiktok"))
            title = str(args.get("title", "Untitled"))
            description = str(args.get("description", ""))
            tags = list(args.get("tags") or [])
            assets_media = dict(args.get("assets") or args.get("media") or {"video": "auto", "subs": "auto", "thumb": "auto"})
            schedule_ts = args.get("schedule_ts")

            if mode in ("rest", "auto"):
                try:
                    body = json.dumps({
                        "platform": platform,
                        "title": title,
                        "description": description,
                        "tags": tags,
                        "media": assets_media,
                        "schedule_ts": schedule_ts
                    }).encode("utf-8")
                    req = urllib.request.Request("http://127.0.0.1:8000/social/kit/build", data=body, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        result = json.loads(r.read().decode("utf-8"))
                        if result.get("ok"): 
                            _passport("social.kit.build", {"ok": True, "platform": platform, "mode": "rest"})
                            return result
                except Exception:
                    if mode == "rest": raise  # If it's clearly a rest, then it's an error.

            # Fallback na local
            from modules.social.kit import build
            result = build(platform, title, description, tags, assets_media, schedule_ts)
            _passport("social.kit.build", {"ok": result.get("ok", False), "platform": platform, "mode": "local"})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    register("social.kit.build", {"platform": "str", "title": "str"}, {"ok": "bool"}, 10, a_build)

    def a_upload(args: Dict[str, Any]):
        try:
            platform = str(args.get("platform", "youtube"))
            kit_dir = str(args.get("kit_dir", ""))
            body = json.dumps({"platform": platform, "kit_dir": kit_dir}).encode("utf-8")
            req = urllib.request.Request("http://127.0.0.1:8000/social/upload", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=21600) as r:
                result = json.loads(r.read().decode("utf-8"))
            _passport("social.upload", {"ok": result.get("ok", False), "platform": platform})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    register("social.upload", {"platform": "str", "kit_dir": "str"}, {"ok": "bool"}, 5, a_upload)

    def a_creds(args: Dict[str, Any]):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/social/creds/status", timeout=10) as r:
                result = json.loads(r.read().decode("utf-8"))
            _passport("social.creds.status", {"ok": result.get("ok", False)})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    register("social.creds.status", {}, {"ok": "bool"}, 1, a_creds)

    def a_ledger_record(args: Dict[str, Any]):
        try:
            from modules.social.ledger import record
            platform = str(args.get("platform", ""))
            campaign = str(args.get("campaign", ""))
            metric = str(args.get("metric", "views"))
            value = float(args.get("value", 0.0))
            currency = str(args.get("currency", ""))
            extra = dict(args.get("extra") or {})
            result = record(platform, campaign, metric, value, currency, extra)
            _passport("social.ledger.record", {"ok": result.get("ok", False), "metric": metric, "value": value})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    register("social.ledger.record", {"platform": "str", "metric": "str", "value": "float"}, {"ok": "bool"}, 2, a_ledger_record)

    def a_ledger_list(args: Dict[str, Any]):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/social/ledger/list", timeout=10) as r:
                result = json.loads(r.read().decode("utf-8"))
            _passport("social.ledger.list", {"ok": result.get("ok", False), "count": len(result.get("entries", []))})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    register("social.ledger.list", {}, {"ok": "bool"}, 1, a_ledger_list)

    def a_campaign_status(args: Dict[str, Any]):
        try:
            # Novyy ekshen: Sobiraet status kampanii iz ledger i plan
            campaign_id = str(args.get("id", ""))
            # Plan first (if needed)
            plan_result = a_plan({"id": campaign_id}) if args.get("include_plan", True) else {}
            # Zatem ledger list, filtr po campaign
            ledger_result = a_ledger_list({})
            entries = [e for e in ledger_result.get("entries", []) if e.get("campaign") == campaign_id]
            result = {"ok": True, "id": campaign_id, "plan": plan_result, "metrics": entries}
            _passport("social.campaign.status", {"ok": True, "id": campaign_id, "metrics_count": len(entries)})
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    register("social.campaign.status", {"id": "str"}, {"ok": "bool"}, 3, a_campaign_status)

# _reg()




