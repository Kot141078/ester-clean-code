# -*- coding: utf-8 -*-
"""
bridges/internet_access.py — setevoy most Ester (poisk + bezopasnaya vyborochnaya zagruzka HTML).

YaVNYY MOST: c=a+b — vneshniy fakt podtyagivaem protseduroy (b), ne lomaya subektnost “c”.
SKRYTYE MOSTY:
  - Cover&Thomas: ogranichenie kanala — RPM/taymaut/limit bayt, chtoby ne zabit liniyu i ne raznesti pamyat.
  - Ashby: requisite variety — neskolko provayderov (Google CSE → DDGS → DDG API) dayut raznoobrazie, a arbitr — stabilizatsiyu.
ZEMNOY ABZATs (inzheneriya/anatomiya):
  Eto kak postavit klapan+manometr na magistral: davlenie (zaprosy) doziruem, musor (lishnie bayty) filtruem,
  a peregrev (flud/taymauty) gasim do togo, kak “serdtse” (event loop) nachnet aritmit.

Bezopasnye defolty:
- CLOSED_BOX=1 ili WEB_FACTCHECK=never  -> set vyklyuchena polnostyu.
- fetch_html() po umolchaniyu vyklyuchen (WEB_ALLOW_FETCH=0) i rezhet SSRF (lokalkhost/privatnye seti).

ENV (osnovnye):
  WEB_FACTCHECK=auto|always|never
  WEB_MAX_RPM=12
  WEB_TIMEOUT_SEC=8
  WEB_MAX_BYTES=800000
  WEB_USER_AGENT="Ester/1.0"
  WEB_PROVIDER=auto|google_cse|ddgs|ddg_api
  WEB_ALLOW_FETCH=0|1
  GOOGLE_API_KEY=...
  GOOGLE_CSE_ID=...
"""

from __future__ import annotations

import json
import os
import re
import time
import threading
import ipaddress
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from duckduckgo_search import DDGS  # type: ignore
except Exception:
    DDGS = None  # type: ignore


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str
    source: str = "web"


class _RateLimiter:
    def __init__(self, max_per_min: int) -> None:
        self.max_per_min = max(1, int(max_per_min or 1))
        self._lock = threading.Lock()
        self._ts: List[float] = []

    def allow(self) -> bool:
        now = time.time()
        cutoff = now - 60.0
        with self._lock:
            self._ts = [t for t in self._ts if t >= cutoff]
            if len(self._ts) >= self.max_per_min:
                return False
            self._ts.append(now)
            return True


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    if not v:
        return bool(default)
    return v in ("1", "true", "yes", "y", "on")


def _is_private_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if not h:
        return True
    if h in ("localhost", "localhost."):
        return True
    # raw ip?
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except Exception:
        pass
    # obvious local zones
    if h.endswith(".local") or h.endswith(".localhost") or h.endswith(".internal"):
        return True
    return False


class InternetAccess:
    def __init__(self) -> None:
        self.web_factcheck = (os.getenv("WEB_FACTCHECK", "auto") or "auto").strip().lower()
        self.max_rpm = int(os.getenv("WEB_MAX_RPM", "12") or "12")
        self.timeout = float(os.getenv("WEB_TIMEOUT_SEC", "8") or "8")
        self.max_bytes = int(os.getenv("WEB_MAX_BYTES", "800000") or "800000")
        self.ua = (os.getenv("WEB_USER_AGENT", "") or "").strip() or "Ester/1.0"
        self.provider = (os.getenv("WEB_PROVIDER", "auto") or "auto").strip().lower()
        self.allow_fetch = _env_bool("WEB_ALLOW_FETCH", False)
        self.google_api_key = (os.getenv("GOOGLE_API_KEY", "") or "").strip()
        self.google_cse_id = (os.getenv("GOOGLE_CSE_ID", "") or "").strip()
        self._rl = _RateLimiter(self.max_rpm)

    def enabled(self) -> bool:
        if _env_bool("CLOSED_BOX", False):
            return False
        if self.web_factcheck == "never":
            return False
        return True

    def google_configured(self) -> bool:
        return bool(self.google_api_key and self.google_cse_id)

    # ---------- low-level ----------
    def _http_get(self, url: str, accept: str = "*/*") -> Optional[bytes]:
        if not self._rl.allow():
            return None
        try:
            req = Request(url, headers={"User-Agent": self.ua, "Accept": accept})
            with urlopen(req, timeout=self.timeout) as resp:
                data = resp.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                return data[: self.max_bytes]
            return data
        except Exception:
            return None

    def _http_get_json(self, url: str) -> Optional[Dict[str, Any]]:
        raw = self._http_get(url, accept="application/json")
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception:
            return None

    # ---------- search providers ----------
    def _search_google_cse_urllib(self, query: str, max_results: int) -> List[WebResult]:
        if not self.google_configured():
            return []
        params = {
            "key": self.google_api_key,
            "cx": self.google_cse_id,
            "q": query,
            "num": str(max(1, min(10, int(max_results)))),
            "safe": "off",
        }
        url = "https://www.googleapis.com/customsearch/v1?" + urlencode(params)
        j = self._http_get_json(url)
        if not j:
            return []
        items = j.get("items") or []
        out: List[WebResult] = []
        for it in items:
            try:
                title = str(it.get("title") or "").strip()
                link = str(it.get("link") or "").strip()
                snippet = str(it.get("snippet") or "").strip()
                if not (title or snippet):
                    continue
                out.append(WebResult(title=title, url=link, snippet=snippet, source="google_cse"))
                if len(out) >= max_results:
                    break
            except Exception:
                continue
        return out

    def _search_google_via_existing_bridge(self, query: str, max_results: int) -> List[WebResult]:
        # 1) engines.google_search_bridge.search
        try:
            from engines.google_search_bridge import search as gsearch  # type: ignore
            payload = gsearch(query=query, limit=int(max_results), source="telegram", autonomy={"ester": True})
            if isinstance(payload, dict) and payload.get("ok") and payload.get("items"):
                out: List[WebResult] = []
                for it in payload.get("items") or []:
                    title = str(it.get("title") or "").strip()
                    url = str(it.get("link") or it.get("url") or "").strip()
                    snippet = str(it.get("snippet") or it.get("body") or "").strip()
                    if not (title or snippet):
                        continue
                    out.append(WebResult(title=title, url=url, snippet=snippet, source="google_bridge"))
                    if len(out) >= max_results:
                        break
                return out
        except Exception:
            pass

        # 2) modules.providers.google_cse_adapter.GoogleCSEAdapter
        try:
            from modules.providers.google_cse_adapter import GoogleCSEAdapter  # type: ignore
            ad = GoogleCSEAdapter()
            payload = ad.search(query=query, limit=int(max_results), source="telegram", autonomy={"ester": True})
            if isinstance(payload, dict) and payload.get("ok") and payload.get("items"):
                out: List[WebResult] = []
                for it in payload.get("items") or []:
                    title = str(it.get("title") or "").strip()
                    url = str(it.get("link") or it.get("url") or "").strip()
                    snippet = str(it.get("snippet") or it.get("body") or "").strip()
                    if not (title or snippet):
                        continue
                    out.append(WebResult(title=title, url=url, snippet=snippet, source="google_adapter"))
                    if len(out) >= max_results:
                        break
                return out
        except Exception:
            pass

        return []

    def _search_ddgs(self, query: str, max_results: int) -> List[WebResult]:
        if DDGS is None:
            return []
        try:
            if not self._rl.allow():
                return []
            out: List[WebResult] = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=int(max_results)):
                    title = str(r.get("title") or "").strip()
                    snippet = str(r.get("body") or "").strip()
                    url = str(r.get("href") or "").strip()
                    if not (title or snippet):
                        continue
                    out.append(WebResult(title=title, url=url, snippet=snippet, source="ddgs"))
                    if len(out) >= max_results:
                        break
            return out
        except Exception:
            return []

    def _search_ddg_api(self, query: str, max_results: int) -> List[WebResult]:
        params = {
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "skip_disambig": "1",
        }
        url = "https://api.duckduckgo.com/?" + urlencode(params)
        j = self._http_get_json(url)
        if not j:
            return []
        out: List[WebResult] = []
        abs_txt = str(j.get("AbstractText") or "").strip()
        abs_url = str(j.get("AbstractURL") or "").strip()
        heading = str(j.get("Heading") or "").strip()
        if abs_txt:
            out.append(WebResult(title=heading or "DuckDuckGo", url=abs_url, snippet=abs_txt, source="ddg_api"))

        def _take_topics(x: Any) -> None:
            if isinstance(x, list):
                for it in x:
                    _take_topics(it)
            elif isinstance(x, dict):
                if "Topics" in x:
                    _take_topics(x.get("Topics"))
                    return
                txt = str(x.get("Text") or "").strip()
                first = str(x.get("FirstURL") or "").strip()
                if txt:
                    out.append(WebResult(title=txt[:80], url=first, snippet=txt, source="ddg_api"))

        _take_topics(j.get("RelatedTopics"))

        uniq: List[WebResult] = []
        seen = set()
        for r in out:
            key = (r.title, r.snippet)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(r)
            if len(uniq) >= max_results:
                break
        return uniq

    # ---------- public API ----------
    def search(self, query: str, max_results: int = 5) -> List[WebResult]:
        if not self.enabled():
            return []
        q = (query or "").strip()
        if not q:
            return []
        max_results = max(1, min(10, int(max_results or 5)))

        # provider order
        prov = self.provider
        if prov not in ("auto", "google_cse", "ddgs", "ddg_api"):
            prov = "auto"

        def _uniq(rs: List[WebResult]) -> List[WebResult]:
            out: List[WebResult] = []
            seen = set()
            for r in rs:
                k = (r.title, r.url)
                if k in seen:
                    continue
                seen.add(k)
                out.append(r)
                if len(out) >= max_results:
                    break
            return out

        # 1) google via existing bridges/adapters (preferred if configured)
        if prov in ("auto", "google_cse"):
            rs = self._search_google_via_existing_bridge(q, max_results)
            if rs:
                return _uniq(rs)
            rs = self._search_google_cse_urllib(q, max_results)
            if rs:
                return _uniq(rs)

        # 2) ddgs
        if prov in ("auto", "ddgs"):
            rs = self._search_ddgs(q, max_results)
            if rs:
                return _uniq(rs)

        # 3) ddg api
        rs = self._search_ddg_api(q, max_results)
        return _uniq(rs)

    def fetch_html(self, url: str) -> str:
        """Optsionalno: gruzim HTML stranitsy (tolko esli WEB_ALLOW_FETCH=1)."""
        if not self.enabled() or not self.allow_fetch:
            return ""
        u = (url or "").strip()
        if not u:
            return ""
        try:
            p = urlparse(u)
            if p.scheme not in ("http", "https"):
                return ""
            host = p.hostname or ""
            if _is_private_host(host):
                return ""
        except Exception:
            return ""
        raw = self._http_get(u, accept="text/html,application/xhtml+xml")
        if not raw:
            return ""
        try:
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def extract_headlines(self, url: str, limit: int = 12) -> List[str]:
        html = self.fetch_html(url)
        if not html:
            return []
        limit = max(1, min(40, int(limit or 12)))

        # grubyy, no bystryy HTML text extraction dlya <a> i <h*>:
        # vynimaem tekst, chistim, filtruem musor.
        candidates: List[str] = []

        # h1-h4
        for m in re.finditer(r"<(h[1-4])[^>]*>(.*?)</\1>", html, flags=re.I | re.S):
            t = re.sub(r"<[^>]+>", " ", m.group(2))
            t = re.sub(r"\s+", " ", t).strip()
            if 25 <= len(t) <= 140:
                candidates.append(t)

        # links
        for m in re.finditer(r"<a[^>]+>(.*?)</a>", html, flags=re.I | re.S):
            t = re.sub(r"<[^>]+>", " ", m.group(1))
            t = re.sub(r"\s+", " ", t).strip()
            if 25 <= len(t) <= 140:
                candidates.append(t)

        # drop obvious UI words
        bad = ("vkhod", "registratsiya", "podpis", "menyu", "poisk", "glavnaya", "kontak", "cookie")
        out: List[str] = []
        seen = set()
        for t in candidates:
            lo = t.lower()
            if any(b in lo for b in bad):
                continue
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def format_evidence(results: List[WebResult], max_chars: int = 1800) -> str:
        max_chars = max(200, int(max_chars or 1800))
        if not results:
            return ""
        lines: List[str] = []
        for r in results:
            t = (r.title or "").strip()
            s = (r.snippet or "").strip()
            u = (r.url or "").strip()
            row = f"- {t}: {s}"
            if u:
                row += f" ({u})"
            lines.append(row)
        txt = "\n".join(lines).strip()
        if len(txt) > max_chars:
            txt = txt[: max_chars].rstrip() + "…"
        return txt

    @staticmethod
    def format_headlines(headlines: List[str], url: str = "", max_chars: int = 1800) -> str:
        max_chars = max(200, int(max_chars or 1800))
        if not headlines:
            return ""
        lines = [f"- {h}" for h in headlines]
        if url:
            lines.append(f"(Istochnik: {url})")
        txt = "\n".join(lines).strip()
        if len(txt) > max_chars:
            txt = txt[: max_chars].rstrip() + "…"
        return txt