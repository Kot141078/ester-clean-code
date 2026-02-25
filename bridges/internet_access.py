# -*- coding: utf-8 -*-
"""bridges/internet_access.py - controlled web search/fetch bridge (CSE/SerpApi/DDG).

EXPLICIT BRIDGE (c=a+b):
  a) request cheloveka +
  b) control web-dostup s ogranichitelyami =>
  c) proveryaemaya opora (sources) or chestnyy [SEARCH_EMPTY].

HIDDEN BRIDGES:
  - Cover & Thomas: timeout/max_bytes/max_chars.
  - Ashby: variety through WEB_PROVIDER.
EARTH:
  esli datchik ne dal signal - pishem FAULT, a ne risuem tsifry."""

from __future__ import annotations

import datetime
import hashlib
import ipaddress
import json
import os
import re
import time
import threading
import logging
from dataclasses import dataclass
from html import unescape as html_unescape
from typing import List, Optional
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from modules.policy.network_policy import is_outbound_allowed
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

logger = logging.getLogger("ester.bridges.internet")


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int((os.getenv(name, "") or "").strip() or str(default))
    except Exception:
        return default


def _is_private_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if not h or h == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
    except Exception:
        pass
    return h.endswith(".local") or h.endswith(".lan")


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""


class _RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = max(1, int(rpm or 12))
        self.min_interval = 60.0 / float(self.rpm)
        self._t_last = 0.0

    def allow(self) -> bool:
        now = time.time()
        if self._t_last <= 0.0:
            self._t_last = now
            return True
        dt = now - self._t_last
        if dt >= self.min_interval:
            self._t_last = now
            return True
        time.sleep(max(0.0, self.min_interval - dt))
        self._t_last = time.time()
        return True


class InternetAccess:
    def __init__(self):
        self.provider = (os.getenv("WEB_PROVIDER", "auto") or "auto").strip().lower()
        self.web_factcheck = (os.getenv("WEB_FACTCHECK", "auto") or "auto").strip().lower()
        self.timeout = float(_env_int("WEB_TIMEOUT_SEC", 10))
        self.max_bytes = int(_env_int("WEB_MAX_BYTES", 1_000_000))
        self.ua = os.getenv(
            "WEB_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Ester/2.0",
        )
        self._rl = _RateLimiter(_env_int("WEB_MAX_RPM", 20))

        self.google_api_key = (os.getenv("GOOGLE_API_KEY", "") or "").strip()
        self.google_cse_id = (os.getenv("GOOGLE_CSE_ID", "") or "").strip()
        self.serpapi_key = (os.getenv("SERPAPI_KEY", "") or "").strip()
        self.serpapi_engine = (os.getenv("SERPAPI_ENGINE", "google") or "google").strip()

        self.last_error: str = ""
        self.last_gate: dict = {"allowed": True, "reason": "init", "code": "NET_OUTBOUND_ALLOWED", "action": "init"}

    def enabled(self) -> bool:
        allowed, reason, code = is_outbound_allowed()
        self.last_gate = {"allowed": bool(allowed), "reason": str(reason), "code": str(code), "action": "enabled"}
        return bool(allowed)

    def _deny(self, action: str, reason: str, code: str) -> dict:
        gate = {
            "allowed": False,
            "reason": str(reason or "policy_deny"),
            "code": str(code or "NET_OUTBOUND_DENIED"),
            "action": str(action or "unknown"),
        }
        self.last_gate = gate
        self.last_error = json.dumps(gate, ensure_ascii=False)
        logger.warning(
            "[NET_GATE] deny action=%s code=%s reason=%s",
            gate["action"],
            gate["code"],
            gate["reason"],
        )
        return gate

    def _check_gate(self, action: str) -> tuple[bool, dict]:
        allowed, reason, code = is_outbound_allowed()
        if allowed:
            gate = {
                "allowed": True,
                "reason": str(reason),
                "code": str(code),
                "action": str(action),
            }
            self.last_gate = gate
            return True, gate
        return False, self._deny(action, reason, code)

    def google_configured(self) -> bool:
        return bool(self.google_api_key and self.google_cse_id)

    def serpapi_configured(self) -> bool:
        return bool(self.serpapi_key)

    def _http_get(self, url: str, accept: str = "*/*") -> Optional[bytes]:
        allowed, _gate = self._check_gate("_http_get")
        if not allowed:
            return None
        if not self._rl.allow():
            return None
        try:
            req = Request(url, headers={"User-Agent": self.ua, "Accept": accept})
            with urlopen(req, timeout=self.timeout) as resp:
                data = resp.read(self.max_bytes + 1)
            return data[: self.max_bytes]
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"[_http_get] Error fetching {url}: {e}")
            return None

    def _http_get_json(self, url: str) -> Optional[dict]:
        b = self._http_get(url, accept="application/json")
        if not b:
            return None
        try:
            return json.loads(b.decode("utf-8", "ignore"))
        except Exception:
            return None

    def _search_google_cse_urllib(self, query: str, max_results: int) -> List[WebResult]:
        if not self.google_configured():
            return []
        max_results = max(1, min(10, int(max_results or 5)))
        params = {"key": self.google_api_key, "cx": self.google_cse_id, "q": query, "num": str(max_results)}
        url = "https://www.googleapis.com/customsearch/v1?" + urlencode(params)
        j = self._http_get_json(url)
        if not j:
            return []
        out: List[WebResult] = []
        for it in (j.get("items") or []):
            link = str(it.get("link") or "").strip()
            if not link:
                continue
            p = urlparse(link)
            if p.scheme not in ("http", "https") or _is_private_host(p.hostname or ""):
                continue
            title = str(it.get("title") or link).strip()
            snip = str(it.get("snippet") or "").strip()
            out.append(WebResult(title=title, url=link, snippet=snip, source="google_cse"))
        return out

    def _search_serpapi(self, query: str, max_results: int) -> List[WebResult]:
        if not self.serpapi_configured():
            return []
        max_results = max(1, min(10, int(max_results or 5)))
        params = {"engine": self.serpapi_engine or "google", "q": query, "api_key": self.serpapi_key, "num": str(max_results)}
        url = "https://serpapi.com/search.json?" + urlencode(params)
        j = self._http_get_json(url)
        if not j:
            return []
        out: List[WebResult] = []
        for it in (j.get("organic_results") or []):
            link = str(it.get("link") or "").strip()
            if not link:
                continue
            p = urlparse(link)
            if p.scheme not in ("http", "https") or _is_private_host(p.hostname or ""):
                continue
            title = str(it.get("title") or link).strip()
            snip = str(it.get("snippet") or "").strip()
            out.append(WebResult(title=title, url=link, snippet=snip, source="serpapi"))
            if len(out) >= max_results:
                break
        return out

    def _search_ddgs(self, query: str, max_results: int) -> List[WebResult]:
        allowed, _gate = self._check_gate("_search_ddgs")
        if not allowed:
            return []
        try:
            from ddgs import DDGS
        except Exception as e:
            self.last_error = f"ddgs import failed: {e}"
            logger.error(f"[DDGS] ddgs import failed: {e}")
            return []

        max_results = max(1, min(10, int(max_results or 5)))
        region = os.getenv("DDGS_REGION", "us-en")
        safesearch = os.getenv("DDGS_SAFESEARCH", "off")
        timelimit = os.getenv("DDGS_TIMELIMIT", "w")

        out: List[WebResult] = []
        try:
            with DDGS() as ddgs:
                try:
                    it = ddgs.text(query, region=region, safesearch=safesearch, timelimit=timelimit, max_results=max_results)
                except TypeError:
                    it = ddgs.text(query, max_results=max_results)
                results = list(it) if it is not None else []
            for r in results:
                u = str(r.get("href") or r.get("url") or "").strip()
                if not u:
                    continue
                p = urlparse(u)
                if p.scheme not in ("http", "https") or _is_private_host(p.hostname or ""):
                    continue
                out.append(WebResult(
                    title=str(r.get("title") or u).strip(),
                    url=u,
                    snippet=str(r.get("body") or r.get("snippet") or "").strip(),
                    source="ddgs",
                ))
        except Exception as e:
            self.last_error = f"ddgs search failed: {e}"
            logger.error(f"[DDGS] Search failed: {e}")
            return []
        return out

    def _search_ddg_api(self, query: str, max_results: int) -> List[WebResult]:
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        url = "https://api.duckduckgo.com/?" + urlencode(params)
        j = self._http_get_json(url)
        if not j:
            return []
        out: List[WebResult] = []
        for rt in (j.get("RelatedTopics") or []):
            if isinstance(rt, dict) and "FirstURL" in rt:
                u = str(rt.get("FirstURL") or "").strip()
                if not u:
                    continue
                p = urlparse(u)
                if p.scheme not in ("http", "https") or _is_private_host(p.hostname or ""):
                    continue
                out.append(WebResult(title=str(rt.get("Text") or u), url=u, snippet="", source="ddg_api"))
                if len(out) >= max_results:
                    break
        return out

    def search(self, query: str, max_results: int = 5) -> List[WebResult]:
        allowed, _gate = self._check_gate("search")
        if not allowed:
            return []
        q = (query or "").strip()
        if not q:
            return []
        p = (self.provider or "auto").strip().lower()

        def _uniq(rs: List[WebResult]) -> List[WebResult]:
            seen = set()
            out: List[WebResult] = []
            for r in rs:
                u = (r.url or "").strip()
                if not u or u in seen:
                    continue
                seen.add(u)
                out.append(r)
            return out

        if p in ("auto", "google_cse") and self.google_configured():
            rs = self._search_google_cse_urllib(q, max_results)
            if rs:
                return _uniq(rs)

        if p in ("auto", "serpapi") and self.serpapi_configured():
            rs = self._search_serpapi(q, max_results)
            if rs:
                return _uniq(rs)

        if p in ("auto", "ddgs"):
            rs = self._search_ddgs(q, max_results)
            if rs:
                return _uniq(rs)

        return _uniq(self._search_ddg_api(q, max_results))

    def get_digest_for_llm(self, query: str, max_results: int = 5) -> str:
        results = self.search(query, max_results)

        # simple relevance filter (works with WebResult, not dict)
        try:
            ql = (query or "").lower()
            tokens = re.findall(r"[a-z0-9]{3,}|[a-ya0-9]{3,}", ql)
            stop = {"latest","stable","current","price","version","now","today","what","who","the","is","of","in","on","at","as"}
            tokens = [t for t in tokens if t not in stop]
            if tokens and results:
                filt: List[WebResult] = []
                for r in results:
                    blob = f"{r.title} {r.snippet} {r.url}".lower()
                    if any(t in blob for t in tokens):
                        filt.append(r)
                results = filt
        except Exception:
            pass

        if not results:
            gate = dict(self.last_gate or {})
            if gate and not bool(gate.get("allowed", True)):
                payload = {
                    "code": str(gate.get("code") or "NET_OUTBOUND_DENIED"),
                    "reason": str(gate.get("reason") or "policy_deny"),
                    "action": str(gate.get("action") or "search"),
                    "query": str(query or ""),
                }
                return "[SEARCH_DENIED] " + json.dumps(payload, ensure_ascii=False)
            return f"[SEARCH_EMPTY] no results for: {query}"

        digest = f"### Web Search Results: '{query}'"
        for i, r in enumerate(results, 1):
            digest += f"{i}. **{r.title}**\n   {r.snippet}\n   [Source: {r.url}]\n\n"
        return digest

    def fetch_html(self, url: str) -> str:
        allowed, _gate = self._check_gate("fetch_html")
        if not allowed:
            return ""
        if not _env_bool("WEB_ALLOW_FETCH", False):
            return ""
        u = (url or "").strip()
        try:
            p = urlparse(u)
            if p.scheme not in ("http", "https") or _is_private_host(p.hostname or ""):
                return ""
        except Exception:
            return ""
        data = self._http_get(u, accept="text/html,application/xhtml+xml")
        if not data:
            return ""
        return data.decode("utf-8", "ignore")

    @staticmethod
    def _html_to_text(html: str) -> str:
        if not html:
            return ""
        try:
            html = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
            html = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
            html = re.sub(r"(?is)<[^>]+>", " ", html)
            txt = html_unescape(html)
            txt = re.sub(r"\s+", " ", txt).strip()
            return txt
        except Exception:
            return ""

    def read_text(self, url: str, max_chars: int = 12000) -> str:
        max_chars = max(400, int(max_chars or 12000))
        html = self.fetch_html(url)
        if not html:
            return ""
        txt = self._html_to_text(html)
        if not txt:
            return ""

        # Hook -> analyst (non-blocking)
        try:
            from modules.analyst import analyst_unit
            if getattr(analyst_unit, "active", False):
                threading.Thread(
                    target=analyst_unit.process_incoming_data,
                    args=(txt, f"web_fetch:{url}"),
                    daemon=True
                ).start()
        except Exception:
            pass

        if len(txt) > max_chars:
            txt = txt[:max_chars].rstrip() + "…"
        return txt

    def ingest_url_to_markdown(self, url: str, out_dir: str, query: str = "", max_chars: int = 18000) -> dict:
        u = (url or "").strip()
        if not u:
            return {"ok": False, "error": "empty_url"}
        allowed, gate = self._check_gate("ingest_url_to_markdown")
        if not allowed:
            return {
                "ok": False,
                "error": str(gate.get("code") or "NET_OUTBOUND_DENIED"),
                "code": str(gate.get("code") or "NET_OUTBOUND_DENIED"),
                "reason": str(gate.get("reason") or "policy_deny"),
                "action": str(gate.get("action") or "ingest_url_to_markdown"),
            }

        txt = self.read_text(u, max_chars=max_chars)
        if not txt:
            return {"ok": False, "error": "fetch_disabled_or_empty"}

        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            return {"ok": False, "error": "cannot_create_out_dir"}

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", (urlparse(u).path or "").strip("/"))[:60] or "page"
        h = hashlib.sha256((u + "\n" + txt[:2000]).encode("utf-8", "ignore")).hexdigest()[:12]
        fn = f"{ts}_{slug}_{h}.md"
        path = os.path.join(out_dir, fn)

        md_lines = [
            "---",
            f"url: {u}",
            f"query: {query}",
            f"fetched_at: {datetime.datetime.now().isoformat()}",
            f"provider: {self.provider}",
            "---",
            "",
            "# Web Ingest",
            "",
            txt,
        ]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines))
        except Exception as e:
            return {"ok": False, "error": f"write_failed: {e}"}

        return {"ok": True, "path": path, "chars": len(txt)}


internet = InternetAccess()
