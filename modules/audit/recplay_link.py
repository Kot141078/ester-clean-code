# -*- coding: utf-8 -*-
"""
modules/audit/recplay_link.py — skvoznoy audit REC→PLAY.

Naznachenie:
- Svyazat zapisannye sobytiya (REC) s fakticheskimi shagami ispolneniya workflow (PLAY).
- Save svodnyy otchet: sopostavlenie, dlitelnosti, uspekh/oshibka.

Khranilische:
- data/audit/recplay/<audit_id>.json   — svodka
- data/audit/recplay/rec_index.json     — indeks poslednikh N auditov

API (cherez routes/audit_recplay_routes.py):
- run_with_audit(workflow, session) → audit_id, report
- get_report(audit_id) → svodka
- list_reports() → poslednie elementy

MOSTY:
- Yavnyy: (Memory ↔ Deystvie) sopostavlyaem to, chto zapisali, s tem, chto vypolnili.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) raskhozhdeniya vidny chislami — umenshenie entropii «kazhetsya, chto rabotaet».
- Skrytyy #2: (Kibernetika ↔ Kontrol) petlya «nablyuday–sopostavlyay–uluchshay» dlya makrosov/vorkflou.

ZEMNOY ABZATs:
Fayly JSON, oflayn. Zapusk workflow vypolnyaem kak obychnyy `/rpa/workflows/run`, no oborachivaem taymerami i svyazyvaem sobytiya po tipu/argumentam.

# c=a+b
"""
from __future__ import annotations
import os, json, time, uuid, http.client
from typing import Dict, Any, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
AUD_DIR = os.path.join(ROOT, "data", "audit", "recplay")
os.makedirs(AUD_DIR, exist_ok=True)

def _idx_path() -> str:
    return os.path.join(AUD_DIR, "rec_index.json")

def _save_idx(item: Dict[str, Any]) -> None:
    idx_p = _idx_path()
    arr: List[Dict[str, Any]] = []
    if os.path.exists(idx_p):
        try:
            with open(idx_p, "r", encoding="utf-8") as f:
                arr = json.load(f)
        except Exception:
            arr = []
    arr.insert(0, item)
    arr = arr[:100]  # khranit poslednie 100
    with open(idx_p, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)

def _read_session_events(session: str) -> List[Dict[str, Any]]:
    # sm. modules/thinking/recorder.py
    rec_p = os.path.join(ROOT, "data", "workflows", "records", f"{session}.json")
    if not os.path.exists(rec_p):
        return []
    with open(rec_p, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return list(obj.get("events", []))

def _post_json(path: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=20.0)
    body = json.dumps(payload)
    conn.request("POST", path, body=body, headers={"Content-Type":"application/json"})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8","ignore")
    conn.close()
    try:
        return resp.status, json.loads(data)
    except Exception:
        return resp.status, {"ok": False, "raw": data}

def run_with_audit(workflow: str, session: str) -> Dict[str, Any]:
    audit_id = str(uuid.uuid4())
    t0 = time.time()
    rec_events = _read_session_events(session)
    # Zapusk workflow obychnym sposobom
    code, run_res = _post_json("/rpa/workflows/run", {"name": workflow})
    t1 = time.time()

    # Sopostavlenie: prostoy khesh po tipu shaga
    def key_ev(ev: Dict[str, Any]) -> str:
        t = ev.get("type")
        if t == "click": return f"click:{int(ev.get('x',0))}:{int(ev.get('y',0))}"
        if t == "type":  return f"type:{len(ev.get('text',''))}"
        if t == "hotkey":return f"hotkey:{ev.get('seq','')}"
        if t == "open":  return f"open:{ev.get('app','')}"
        if t == "ocr_click": return f"ocr:{ev.get('needle','')}"
        if t == "macro": return f"macro:{ev.get('name','')}"
        return f"{t}"

    # Otvet ispolnitelya mozhet soderzhat trassu, esli realizovano; inache sopostavim po dline/tipam
    wf_trace = list(run_res.get("trace", [])) if isinstance(run_res, dict) else []
    m = []
    used = set()
    # legkoe sopostavlenie po klyucham
    for i, ev in enumerate(rec_events):
        kev = key_ev(ev)
        hit = {"rec_idx": i, "rec_key": kev, "play_idx": None, "status": "miss"}
        for j, st in enumerate(wf_trace):
            if j in used: 
                continue
            kst = st.get("key") or st.get("macro") or st.get("type")
            if isinstance(kst, dict):
                kst = kst.get("macro") or kst.get("type")
            if kst and str(kst).lower().startswith(kev.split(":")[0]):  # po tipu
                hit["play_idx"] = j
                hit["status"] = "match"
                used.add(j)
                break
        m.append(hit)

    ok = bool(code == 200 and run_res.get("ok", False))
    report = {
        "audit_id": audit_id,
        "ok": ok,
        "workflow": workflow,
        "session": session,
        "rec_count": len(rec_events),
        "play_count": len(wf_trace) if wf_trace else None,
        "duration_sec": round(t1 - t0, 3),
        "map": m,
        "run_raw": run_res if ok else {"status": code, **run_res}
    }
    out_p = os.path.join(AUD_DIR, f"{audit_id}.json")
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    _save_idx({"audit_id": audit_id, "ts": int(t1), "workflow": workflow, "session": session, "ok": ok})
    return {"ok": True, "audit_id": audit_id, "report_path": out_p, "summary": {"ok": ok, "duration_sec": report["duration_sec"], "matches": sum(1 for x in m if x["status"]=="match")}}