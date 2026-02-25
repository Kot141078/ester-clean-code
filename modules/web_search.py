# -*- coding: utf-8 -*-
"""modules/web_search.py ​​- mnogoistochnikovyy web-poisk (Google CSE / SerpAPI / Bing / DuckDuckGo HTML-fallback).

Zemnoy abzats (inzheneriya):
Eto “vkhod v mir ssylok”: po tekstovomu zaprosu vozvraschaem spisok {title,url,snippet,source}.
Esli klyuchey net - rabotaem cherez legkiy HTML-fallback DuckDuckGo. Nikakikh change
suschestvuyuschikh marshrutov/kontraktov — modul vyzyvaetsya iz thinking-payplayna, net-mostov
or utilities.

Mosty:
- Yavnyy: Poisk ↔ Ingest - rezultatom yavlyayutsya URL, kotorye mozhno srazu otpravit v /ingest (detect_and_read/url).
- Skrytyy 1: Infoteoriya ↔ RAG - naydennye dokumenty vkhodyat v pamyat, uluchshayut pokrytie dlya posleduyuschikh zaprosov.
- Skrytyy 2: Bezopasnost ↔ Politiki — A/B-slot i deny-spisok domenov predotvraschayut utechki/riskovannye istochniki.

A/B-slot (bezopasnaya samo-redaktura):
- SEARCH_AB = "A" (by umolchaniyu): vklyucheny provaydery, est bezopasnyy HTML-fallback;
- SEARCH_AB = "B": vozvrat pustogo spiska (signal "poisk vyklyuchen"), avtokatbek — peremennaya okruzheniya.

# c = a + b"""

from __future__ import annotations

import json
import os
import re
import html as _html_mod
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, unquote_plus
import urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- ENV / konfig ---

SEARCH_PROVIDER = (os.getenv("SEARCH_PROVIDER", "").strip().lower())  # "", "google", "serpapi", "bing", "ddg"
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
BING_API_KEY = os.getenv("BING_API_KEY", "")
DDG_HTML_ENDPOINT = os.getenv("DDG_HTML_ENDPOINT", "https://duckduckgo.com/html/")
SEARCH_AB = (os.getenv("SEARCH_AB", "A") or "A").upper()
SEARCH_TIMEOUT = float(os.getenv("SEARCH_TIMEOUT", "8.0"))
SEARCH_TOPK_MAX = int(os.getenv("SEARCH_TOPK_MAX", "10"))
DENY_DOMAINS = {
    x.strip().lower()
    for x in (os.getenv("SEARCH_DENY_DOMAINS", "") or "").split(",")
    if x.strip()
}

_UA = "EsterWebSearch/1.0"


def _http_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 8.0) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "ignore") or "{}"
    try:
        return json.loads(body)
    except Exception:
        return {}


def _http_text(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 8.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _ok_url(u: str) -> bool:
    if not u or not isinstance(u, str):
        return False
    low = u.lower()
    if not low.startswith(("http://", "https://")):
        return False
    host = re.sub(r"^https?://", "", low).split("/")[0]
    host = host.split(":")[0]
    if host in DENY_DOMAINS:
        return False
    return True


def _norm_item(title: str, url: str, snippet: str, source: str) -> Dict[str, str]:
    return {
        "title": (title or "").strip(),
        "url": (url or "").strip(),
        "snippet": re.sub(r"\s+", " ", (snippet or "").strip()),
        "source": source,
    }


# --- Provaydery ---


def _search_google_cse(q: str, topk: int) -> List[Dict[str, str]]:
    if not (GOOGLE_CSE_ID and GOOGLE_API_KEY):
        return []
    params = {
        "q": q,
        "cx": GOOGLE_CSE_ID,
        "key": GOOGLE_API_KEY,
        "num": max(1, min(topk, 10)),
        "safe": "off",
    }
    url = "https://www.googleapis.com/customsearch/v1?" + urlencode(params)
    j = _http_json(url, timeout=SEARCH_TIMEOUT)
    out: List[Dict[str, str]] = []
    for it in j.get("items") or []:
        link = it.get("link") or ""
        if not _ok_url(link):
            continue
        out.append(
            _norm_item(
                it.get("title") or link,
                link,
                it.get("snippet") or "",
                "google",
            )
        )
        if len(out) >= topk:
            break
    return out


def _search_serpapi(q: str, topk: int) -> List[Dict[str, str]]:
    if not SERPAPI_KEY:
        return []
    params = {
        "q": q,
        "engine": "google",
        "api_key": SERPAPI_KEY,
        "num": max(1, min(topk, 10)),
    }
    url = "https://serpapi.com/search.json?" + urlencode(params)
    j = _http_json(url, timeout=SEARCH_TIMEOUT)
    out: List[Dict[str, str]] = []
    for it in (j.get("organic_results") or []):
        link = it.get("link") or ""
        if not _ok_url(link):
            continue
        out.append(
            _norm_item(
                it.get("title") or link,
                link,
                it.get("snippet") or "",
                "serpapi",
            )
        )
        if len(out) >= topk:
            break
    return out


def _search_bing(q: str, topk: int) -> List[Dict[str, str]]:
    if not BING_API_KEY:
        return []
    params = {
        "q": q,
        "count": max(1, min(topk, 10)),
    }
    url = "https://api.bing.microsoft.com/v7.0/search?" + urlencode(params)
    j = _http_json(url, headers={"Ocp-Apim-Subscription-Key": BING_API_KEY}, timeout=SEARCH_TIMEOUT)
    out: List[Dict[str, str]] = []
    for it in ((j.get("webPages") or {}).get("value") or []):
        link = it.get("url") or ""
        if not _ok_url(link):
            continue
        out.append(
            _norm_item(
                it.get("name") or link,
                link,
                it.get("snippet") or "",
                "bing",
            )
        )
        if len(out) >= topk:
            break
    return out


def _search_ddg_html(q: str, topk: int) -> List[Dict[str, str]]:
    """Legkiy HTML-scrape DuckDuckGo — fallback bez klyuchey.

    Zdes delaem maksimalno terpimyy regeksp: ischem lyuboy <a>, u kotorogo
    v spiske klassov est slovo "result__a". So on perezhivaet added
    novykh klassov (js-result-title-link i pr.)."""
    params = {"q": q, "kl": "wt-wt"}  # world-wide
    url = DDG_HTML_ENDPOINT + "?" + urlencode(params)
    html_text = _http_text(url, timeout=SEARCH_TIMEOUT)

    items: List[Dict[str, str]] = []
    # Primernyy fragment:
    # <a class="result__a js-result-title-link ..." href="...">Title</a>
    pattern = (
        r'<a[^>]+class="[^"]*\bresult__a\b[^"]*"[^>]+href="([^"]+)"[^>]*>'  # href
        r'(.*?)'  # inner HTML (title)
        r"</a>"
    )

    for m in re.finditer(pattern, html_text, flags=re.I | re.S):
        href = _html_mod.unescape(m.group(1) or "")
        title_html = _html_mod.unescape(m.group(2) or "")
        title = re.sub("<[^>]+>", "", title_html).strip()

        u = href
        m2 = re.search(r"uddg=([^&]+)", href)
        if m2:
            try:
                u = unquote_plus(m2.group(1))
            except Exception:
                pass

        if not _ok_url(u):
            continue

        items.append(_norm_item(title or u, u, "", "ddg"))
        if len(items) >= topk:
            break
    return items


# --- Public function ---


def search_web(query: str, topk: int = 5) -> List[Dict[str, str]]:
    """Unifitsirovannyy web-search.
    Vozvraschaet spisok obektov {title,url,snippet,source}.

    Poryadok provayderov:
      - yavnyy SEARCH_PROVIDER ("google","serpapi","bing","ddg"),
      - auto-pick: Google -> SerpAPI -> Bing -> DDG.

    A/B:
      - A (default): ispolzuem dostupnye provaydery/folbek.
      - B: vozvraschaem [] (poisk otklyuchen)."""
    q = (query or "").strip()
    if not q:
        return []

    try:
        topk_int = int(topk or 5)
    except Exception:
        topk_int = 5
    topk_int = max(1, min(topk_int, SEARCH_TOPK_MAX))

    if SEARCH_AB == "B":
        # Disabling search completely - safe mode.
        return []

    prov = SEARCH_PROVIDER
    tried: List[str] = []

    def _try(fn, name: str) -> List[Dict[str, str]]:
        tried.append(name)
        try:
            r = fn(q, topk_int)
            if r:
                return r
        except Exception:
            return []
        return []

    # Explicit provider
    if prov == "google":
        r = _try(_search_google_cse, "google")
        return r
    if prov == "serpapi":
        r = _try(_search_serpapi, "serpapi")
        return r
    if prov == "bing":
        r = _try(_search_bing, "bing")
        return r
    if prov == "ddg":
        r = _try(_search_ddg_html, "ddg")
        return r

    # Auto-pick: Google -> SerpAPI -> Bing -> DDG
    for fn, name in [
        (_search_google_cse, "google"),
        (_search_serpapi, "serpapi"),
        (_search_bing, "bing"),
        (_search_ddg_html, "ddg"),
    ]:
        r = _try(fn, name)
        if r:
            return r

    return []