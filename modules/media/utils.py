# -*- coding: utf-8 -*-
"""modules/media/utils.py - utility dlya media: id, shell, kvoty, legalnyy storozh, profile, KG/pamyat.

Mosty:
- Yavnyy: (Media ↔ Infrastruktura) obschiy sloy dlya IngestGuard/LegalGuard/Passport/Memory/KG.
- Skrytyy #1: (RAG ↔ Kontent) umeet dobavlyat dokumenty v fallback-dok-khranilische poiska.
- Skrytyy #2: (SelfCatalog ↔ Prozrachnost) odinakovaya tochka zhurnalirovaniya.

Zemnoy abzats:
Servisnyy “karkas” - prezhde chem trogat tyazhelye fayly i set, ask “mozhno?”, a potom vse chestno zadokumentirovat.
Obedineno iz dvukh versiy: additional fallback'y dlya robustness, logirovanie dlya pamyati Ester.

# c=a+b"""
from __future__ import annotations
import os, json, hashlib, time, subprocess, shlex, urllib.request, urllib.error
import logging
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Setting up logging for error “memory” in Esther
logging.basicConfig(filename=os.getenv("MEDIA_LOG", "data/logs/media_utils.log"), level=logging.ERROR,
                    format="%(asctime)s - %(levelname)s - %(message)s")

MEDIA_DB  = os.getenv("MEDIA_DB", "data/media/index.json")
MEDIA_DIR = os.getenv("MEDIA_DIR", "data/media/objects")
APPEND_RAG = os.getenv("MEDIA_APPEND_RAG", "true").lower() == "true"
HYBRID_DOCS = os.getenv("HYBRID_FALLBACK_DOCS", "data/mem/docs.jsonl")

def _json_url(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    """Universal HTTP helper for requests to a local server, from false to an empty remote."""
    data = None if payload is None else json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8000" + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        logging.error(f"HTTP error in _json_url for {path}: {str(e)}")
        return {}

def ensure_db():
    os.makedirs(os.path.dirname(MEDIA_DB), exist_ok=True)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    if not os.path.isfile(MEDIA_DB):
        json.dump({"items": []}, open(MEDIA_DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def load_db(): ensure_db(); return json.load(open(MEDIA_DB, "r", encoding="utf-8"))
def save_db(j): json.dump(j, open(MEDIA_DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def vid_id(s: str) -> str:
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
    return f"V{h}"

def shell(cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")
    except subprocess.TimeoutExpired:
        p.kill()
        return 124, "", "timeout"
    except Exception as e:
        logging.error(f"Shell error for cmd '{cmd}': {str(e)}")
        return 1, "", str(e)

def legal_check(kind: str, target: str) -> dict:
    # First we try HTTP, if not, fake it on a local day-list (extension for Robustness Esther)
    try:
        payload = {"task": {"kind": kind, "target": target, "notes": "media_pipeline"}}
        rep = _json_url("/policy/legal/check", payload, 10)
        if rep.get("ok", False):
            return rep
    except Exception:
        pass
    # Falbatsk: simple local check, like in the old version
    deny_hosts = {"piratebay", "rut*", "kinovibe.vip*"}  # Expand according to Esther's rules
    verdict = "allow"
    for h in deny_hosts:
        if h.strip("*").lower() in (target or "").lower():
            verdict = "deny"; break
    return {"ok": True, "verdict": verdict, "reasons": [], "service": target, "kind": kind}

def ingest_quota(source: str, cost: int) -> dict:
    payload = {"source": source, "cost": cost}
    rep = _json_url("/ingest/guard/check", payload, 10)
    if rep:
        return rep
    return {"ok": True, "allowed": True, "left": 0}  # Graceful fallback

def passport(note: str, meta: dict, source: str):
    payload = {"note": note, "meta": meta, "source": source}
    try:
        _json_url("/mem/passport/append", payload, 5)
    except Exception:
        logging.error(f"Passport append failed for note '{note}'")
        pass  # Ne lomaem protsess, Ester pomnit kontekst

def mem_append(text: str, meta: dict) -> None:
    # best-effort: if there is mm.add_text - use it, with false
    try:
        from services.mm_access import get_mm  # type: ignore
        mm = get_mm()
        add = getattr(mm, "add_text", None)
        if callable(add):
            add(text, meta)
    except Exception as e:
        logging.error(f"mem_append failed: {str(e)}")
        pass

def kg_autolink(items: list[dict]) -> None:
    if os.getenv("MEDIA_AUTOLINK", "true").lower() != "true": return
    payload = {"items": items}
    try:
        _json_url("/mem/kg/autolink", payload, 10)
    except Exception:
        logging.error("kg_autolink failed")
        pass  # Graceful, ne fragmentiruem

def rag_append(doc_id: str, text: str):
    if not APPEND_RAG: return
    try:
        os.makedirs(os.path.dirname(HYBRID_DOCS), exist_ok=True)
        with open(HYBRID_DOCS, "a", encoding="utf-8") as f:
            # Limit text for security, like the old version
            f.write(json.dumps({"id": doc_id, "text": text[:8000]}, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.error(f"rag_append failed for doc_id '{doc_id}': {str(e)}")
# pass