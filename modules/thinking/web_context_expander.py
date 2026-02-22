# -*- coding: utf-8 -*-
"""modules/thinking/web_context_expander.py — rasshiritel konteksta (web search → optional read → optional ingest).

API:
  - expand(q: str, k: int = 5, autofetch: bool = False, max_fetch: int = 3, read_content: bool = True) -> dict
  - counters() -> dict
  - reset_counters() -> dict

A/B:
  - WEB_CONTEXT_AB=A — polnotsennaya rabota (po umolchaniyu).
  - WEB_CONTEXT_AB=B — tolko plan (bez vyzovov ingest endpoyntov).

ENV:
  - WEB_CONTEXT_AUTOFETCH=0/1
  - WEB_CONTEXT_ALLOW_HOSTS="example.com,news.site"  (esli zadan — ingest tolko iz allow-list)
  - ESTER_BASE_URL="http://127.0.0.1:8090"
  - URL_INGEST_ENDPOINT="/ingest/url/fetch"
  - VIDEO_INGEST_ENDPOINT="/ingest/video/universal/fetch"
  - WEB_CONTEXT_HTTP_TIMEOUT_SEC=8
  - WEB_CONTEXT_MAX_TEXT=5000

Mosty:
  - Yavnyy: «myshlenie» poluchaet vneshnie ssylki, a pri neobkhodimosti akkuratno kladet istochniki v pamyat cherez ingest.
  - Skrytye:
      1) Infoteoriya ↔ nadezhnost: allow-list + best-effort = kontrol kanala i otsutstvie “zhestkikh” padeniy.
      2) Kibernetika ↔ kontrol: A/B (plan/vypolnenie) upravlyaetsya ENV i prozrachno v schetchikakh.

ZEMNOY ABZATs: vnizu fayla.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# === PATCH: import web_browser dlya chteniya stranits (optsionalno) ===
try:
    from bridges.web_browser import browse, search_and_read, WebPage  # type: ignore
    WEB_BROWSER_AVAILABLE = True
except Exception:
    WEB_BROWSER_AVAILABLE = False
    WebPage = None  # type: ignore
# === END PATCH ===

WEB_CONTEXT_AB = (os.getenv("WEB_CONTEXT_AB", "A") or "A").strip().upper()
AUTO = bool(int(os.getenv("WEB_CONTEXT_AUTOFETCH", "0") or "0"))
ALLOW = {x.strip().lower() for x in (os.getenv("WEB_CONTEXT_ALLOW_HOSTS", "") or "").split(",") if x.strip()}

BASE = (os.getenv("ESTER_BASE_URL", "http://127.0.0.1:8090") or "").strip().rstrip("/")
URL_EP = (os.getenv("URL_INGEST_ENDPOINT", "/ingest/url/fetch") or "").strip()
VID_EP = (os.getenv("VIDEO_INGEST_ENDPOINT", "/ingest/video/universal/fetch") or "").strip()

HTTP_TIMEOUT = int(os.getenv("WEB_CONTEXT_HTTP_TIMEOUT_SEC", "8") or "8")
MAX_TEXT = int(os.getenv("WEB_CONTEXT_MAX_TEXT", "5000") or "5000")

VIDEO_HOST_RE = re.compile(r"(youtube\.com|youtu\.be|vimeo\.com|rutube\.ru|dailymotion\.com|ted\.com)$", re.I)

_CNT: Dict[str, int] = {
    "expand_calls": 0,
    "read_pages": 0,
    "read_ok": 0,
    "read_fail": 0,
    "autofetch_jobs": 0,
    "autofetch_ok": 0,
    "autofetch_fail": 0,
}


def _host(url: str) -> str:
    low = (url or "").lower().strip()
    low = re.sub(r"^https?://", "", low)
    return low.split("/")[0].split(":")[0]


def _ok_for_autofetch(url: str) -> bool:
    h = _host(url)
    if ALLOW:
        return h in ALLOW
    return True  # po umolchaniyu doveryaem; ogranichivay cherez WEB_CONTEXT_ALLOW_HOSTS


def _resolve_post_url(path: str) -> str:
    p = (path or "").strip()
    if not p:
        return BASE
    if p.startswith("http://") or p.startswith("https://"):
        return p
    if not p.startswith("/"):
        p = "/" + p
    return BASE + p


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP POST JSON, best-effort."""
    url = _resolve_post_url(path)
    try:
        import requests  # type: ignore

        r = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            try:
                return {"ok": True, "url": url, "status": 200, "resp": r.json()}
            except Exception:
                return {"ok": True, "url": url, "status": 200, "resp": r.text[:400]}
        return {"ok": False, "url": url, "status": r.status_code, "resp": (r.text or "")[:400]}
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}


def _read_pages(hits: List[Dict[str, Any]], max_fetch: int) -> List[Dict[str, Any]]:
    """Best-effort chtenie stranits cherez bridges.web_browser.browse."""
    out: List[Dict[str, Any]] = []
    if not (WEB_BROWSER_AVAILABLE and hits):
        return out

    n = max(0, min(int(max_fetch), len(hits)))
    for hit in hits[:n]:
        url = (hit or {}).get("url")
        if not url:
            continue
        _CNT["read_pages"] += 1
        try:
            page = browse(url)  # type: ignore
            # page.ok() mozhet otsutstvovat → zaschischaemsya
            ok = bool(getattr(page, "ok", lambda: False)())
            if ok:
                _CNT["read_ok"] += 1
                out.append(
                    {
                        "url": url,
                        "title": getattr(page, "title", None),
                        "text": (getattr(page, "text", "") or "")[:MAX_TEXT],
                        "meta": getattr(page, "meta_description", None),
                    }
                )
            else:
                _CNT["read_fail"] += 1
                out.append({"url": url, "error": "browse_not_ok"})
        except Exception as e:
            _CNT["read_fail"] += 1
            out.append({"url": url, "error": str(e)})
    return out


def expand(
    q: str,
    k: int = 5,
    autofetch: bool = False,
    max_fetch: int = 3,
    read_content: bool = True,
) -> Dict[str, Any]:
    """Rasshiryaet kontekst cherez veb-poisk.

    1) Delaet poisk cherez modules.web_search.search_web
    2) Optsionalno chitaet soderzhimoe top-N stranits (esli bridges.web_browser dostupen)
    3) Optsionalno otpravlyaet top-N URL v ingest endpoints (esli A/B razreshaet)
    """
    from modules.web_search import search_web  # lokalnyy import dlya ustoychivosti

    _CNT["expand_calls"] += 1

    topk = max(1, min(int(k), 10))
    hits = search_web(q, topk=topk) or []

    jobs: List[Dict[str, Any]] = []
    pages_content: List[Dict[str, Any]] = []

    if read_content:
        pages_content = _read_pages(hits, max_fetch=max_fetch)

    do_fetch = AUTO or bool(autofetch)
    if WEB_CONTEXT_AB == "B":
        do_fetch = False

    if do_fetch and hits:
        take = 0
        max_take = max(0, min(int(max_fetch), 10))
        for it in hits:
            if take >= max_take:
                break
            url = (it or {}).get("url") or ""
            if not url or not _ok_for_autofetch(url):
                continue

            h = _host(url)
            if VIDEO_HOST_RE.search(h):
                j = _post(VID_EP, {"url": url, "want": {"subs": True, "summary": True, "meta": True}})
            else:
                j = _post(URL_EP, {"url": url})

            _CNT["autofetch_jobs"] += 1
            if j.get("ok"):
                _CNT["autofetch_ok"] += 1
            else:
                _CNT["autofetch_fail"] += 1

            jobs.append({"url": url, "host": h, "result": j})
            take += 1

    return {
        "ok": True,
        "q": q,
        "items": hits,
        "jobs": jobs,
        "autofetch": do_fetch,
        "pages_content": pages_content,
        "ab": WEB_CONTEXT_AB,
        "web_browser": bool(WEB_BROWSER_AVAILABLE),
    }


def counters() -> Dict[str, int]:
    """Vozvraschaet tekuschie schetchiki (kopiyu)."""
    return dict(_CNT)


def reset_counters() -> Dict[str, int]:
    """Sbrasyvaet schetchiki i vozvraschaet novoe sostoyanie."""
    for k in list(_CNT.keys()):
        _CNT[k] = 0
    return dict(_CNT)


__all__ = ["expand", "counters", "reset_counters"]


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Eto kak podnesti “nos” k realnosti: my nyukhaem mir (search), mozhem pri neobkhodimosti poprobovat na vkus (read),
i tolko potom reshaem — nesti na sklad (ingest) ili prosto zapisat plan. A/B‑tumbler zdes — kak predokhranitel
v schitke: snachala sukhaya proverka, potom vklyuchenie moschnosti.
"""