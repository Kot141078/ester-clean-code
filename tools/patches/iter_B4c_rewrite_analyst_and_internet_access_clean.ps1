<#
B4c — Clean rewrite (PS5-safe) for:
  - modules\analyst.py
  - bridges\internet_access.py

A/B-sloty + avto-otkat:
  A: primenyaem novye versii faylov
  B: esli smoke-test padaet — otkatyvaemsya na bekapy

YaVNYY MOST (c=a+b):
  a) zapros/namerenie (user text) + b) instrumentalnyy most (web) + analiticheskaya ochered => c) proveryaemye fakty/sled.

SKRYTYE MOSTY:
  - Ashby: raznorodnye vkhody privodim k edinomu payload (submit_event).
  - Cover&Thomas: ogranichenie kanala (taymaut/bayty/snippet) chtoby ne utonut.
ZEMNOY:
  kak u termometra: net signala => pishem FAULT, a ne «36.6».
#>

param(
  [string]$ProjectRoot = (Get-Location).Path,
  [switch]$PurgeLegacyDuckDuckGoSearch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host $m -ForegroundColor Cyan }
function Warn($m){ Write-Host $m -ForegroundColor Yellow }

$proj = (Resolve-Path -LiteralPath $ProjectRoot).Path
Info "ProjectRoot: $proj"

$py = Join-Path $proj ".venv\Scripts\python.exe"
if (!(Test-Path $py)) { throw "venv python not found: $py" }

if ($PurgeLegacyDuckDuckGoSearch) {
  Info "[pip] Uninstall legacy duckduckgo-search..."
  try { & $py -m pip uninstall -y duckduckgo-search duckduckgo_search | Out-Host } catch {}
}

# Ensure ddgs present
Info "[pip] Ensure ddgs present..."
& $py -m pip install -U ddgs | Out-Host

$an = Join-Path $proj "modules\analyst.py"
$ia = Join-Path $proj "bridges\internet_access.py"
if (!(Test-Path $an)) { throw "Missing file: $an" }
if (!(Test-Path $ia)) { throw "Missing file: $ia" }

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$bakAn = "$an.bak_$ts"
$bakIa = "$ia.bak_$ts"
Copy-Item -LiteralPath $an -Destination $bakAn -Force
Copy-Item -LiteralPath $ia -Destination $bakIa -Force
Info "Backups:"
Info "  $bakAn"
Info "  $bakIa"

# ---------- New modules/analyst.py ----------
$AnalystPy = @'
# -*- coding: utf-8 -*-
"""
modules/analyst.py — Deep Processing Unit (GPU/CPU safe).

EXPLICIT BRIDGE (c=a+b):
  a) vkhodyaschiy kontent (soobscheniya/veb/fayly) +
  b) protsedurnaya ochered obrabotki/sokhraneniya =>
  c) vosproizvodimyy analiticheskiy sled (JSONL).

HIDDEN BRIDGES:
  - Ashby: raznye vkhody privodim k edinomu payload.
  - Cover & Thomas: ogranichivaem «shirinu kanala» (snippet/metadannye).

EARTH:
  kak zheludochek serdtsa — prinimaet portsiyu i vytalkivaet dalshe; ne blokiruet osnovnoy potok.
"""

from __future__ import annotations

import os
import json
import logging
import threading
from datetime import datetime
from queue import Queue, Empty
from typing import Any, Dict, Optional

logger = logging.getLogger("ester.analyst")

# torch - strictly optional
try:
    import torch  # type: ignore
except Exception:
    torch = None  # type: ignore


def _has_cuda() -> bool:
    try:
        return (torch is not None) and hasattr(torch, "cuda") and torch.cuda.is_available()  # type: ignore
    except Exception:
        return False


HAS_TORCH = torch is not None
HAS_CUDA = _has_cuda()


def cuda_device_count() -> int:
    if not HAS_CUDA:
        return 0
    try:
        return int(torch.cuda.device_count())  # type: ignore
    except Exception:
        return 0


HAS_DUAL_GPU = cuda_device_count() > 1
DEVICE = "cuda:1" if HAS_DUAL_GPU else ("cuda:0" if HAS_CUDA else "cpu")


class EsterAnalyst:
    def __init__(self) -> None:
        self.queue: "Queue[Dict[str, Any]]" = Queue()
        self.active: bool = True
        self.device: str = DEVICE
        logger.info(f"[ANALYST] Initialized on {self.device}. Dual GPU: {HAS_DUAL_GPU}")

        self.worker = threading.Thread(
            target=self._worker_loop, daemon=True, name="Analyst-Worker"
        )
        self.worker.start()

    def submit_event(self, content: str, source: str, meta: Optional[dict] = None) -> None:
        if not content or len(content) < 5:
            return
        payload = {
            "content": content,
            "source": source,
            "meta": meta or {},
            "ts": datetime.now().isoformat(),
        }
        self.queue.put(payload)

    def process_incoming_data(self, *args, **kwargs) -> None:
        """
        Compatibility shim:
          - process_incoming_data(content, source)
          - process_incoming_data(payload_dict)
        """
        try:
            if len(args) == 1 and isinstance(args[0], dict):
                p = args[0]
                self.submit_event(str(p.get("content", "")), str(p.get("source", "unknown")), p.get("meta") or {})
                return
            if len(args) >= 2:
                self.submit_event(str(args[0]), str(args[1]), kwargs.get("meta"))
                return
        except Exception as e:
            logger.error(f"[ANALYST] process_incoming_data failed: {e}")

    def _worker_loop(self) -> None:
        logger.info("[ANALYST] Worker started. Waiting for data...")
        while self.active:
            try:
                task = self.queue.get(timeout=0.5)
            except Empty:
                continue
            try:
                self._process_task(task)
            except Exception as e:
                logger.error(f"[ANALYST] Error in worker: {e}")
            finally:
                try:
                    self.queue.task_done()
                except Exception:
                    pass

    def _process_task(self, task: Dict[str, Any]) -> None:
        content = str(task.get("content", ""))
        source = str(task.get("source", ""))

        sentiment = "neutral"
        keywords = [w for w in content.split() if len(w) > 6 and w.istitle()]

        insight = {
            "timestamp": task.get("ts"),
            "source_type": source,
            "sentiment": sentiment,
            "extracted_keys": list(set(keywords))[:10],
            "snippet": content[:200].replace("\n", " "),
            "full_content_hash": hash(content),
        }

        self._save_insight(insight)

    def _save_insight(self, insight: Dict[str, Any]) -> None:
        path = "data/memory/deep_insights.jsonl"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(insight, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[ANALYST] Save failed: {e}")


analyst = EsterAnalyst()
analyst_unit = analyst
'@

# ---------- New bridges/internet_access.py ----------
$InternetPy = @'
# -*- coding: utf-8 -*-
"""
bridges/internet_access.py — controlled web search/fetch bridge (CSE/SerpApi/DDG).

EXPLICIT BRIDGE (c=a+b):
  a) zapros cheloveka +
  b) kontroliruemyy web-dostup s ogranichitelyami =>
  c) proveryaemaya opora (sources) ili chestnyy [SEARCH_EMPTY].

HIDDEN BRIDGES:
  - Cover & Thomas: timeout/max_bytes/max_chars.
  - Ashby: variety cherez WEB_PROVIDER.
EARTH:
  esli datchik ne dal signal — pishem FAULT, a ne risuem tsifry.
"""

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

    def enabled(self) -> bool:
        if _env_bool("CLOSED_BOX", False):
            return False
        if self.web_factcheck == "never":
            return False
        return True

    def google_configured(self) -> bool:
        return bool(self.google_api_key and self.google_cse_id)

    def serpapi_configured(self) -> bool:
        return bool(self.serpapi_key)

    def _http_get(self, url: str, accept: str = "*/*") -> Optional[bytes]:
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
        if not self.enabled():
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
            return f"[SEARCH_EMPTY] no results for: {query}"

        digest = f"### Web Search Results: '{query}'\n"
        for i, r in enumerate(results, 1):
            digest += f"{i}. **{r.title}**\n   {r.snippet}\n   [Source: {r.url}]\n\n"
        return digest

    def fetch_html(self, url: str) -> str:
        if not self.enabled() or not _env_bool("WEB_ALLOW_FETCH", False):
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
'@

try {
  Info "[A] Write clean analyst.py and internet_access.py"
  Set-Content -LiteralPath $an -Value $AnalystPy -Encoding UTF8
  Set-Content -LiteralPath $ia -Value $InternetPy -Encoding UTF8

  Info "[smoke] analyst import"
  & $py -c "from modules.analyst import analyst_unit, HAS_TORCH, HAS_CUDA, cuda_device_count; print('OK analyst', HAS_TORCH, HAS_CUDA, cuda_device_count()); analyst_unit.submit_event('hello world','smoke'); print('submit ok')"

  Info "[smoke] internet import + ddgs search call"
  & $py -c "from bridges.internet_access import internet; print('OK internet enabled:', internet.enabled()); print(internet.get_digest_for_llm('pytorch latest stable release version site:pytorch.org', 5)[:300])"

  Info "[smoke] ensure duckduckgo_search absent"
  $hit = Select-String -Path $ia -Pattern "duckduckgo_search" -ErrorAction SilentlyContinue
  if ($hit) { throw "duckduckgo_search still present in internet_access.py" }

  Info "[OK] B4c applied successfully."
}
catch {
  Warn "[B] Failed. Rolling back..."
  Copy-Item -LiteralPath $bakAn -Destination $an -Force
  Copy-Item -LiteralPath $bakIa -Destination $ia -Force
  throw
}
