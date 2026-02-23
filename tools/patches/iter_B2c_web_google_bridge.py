# -*- coding: utf-8 -*-
"""
tools/patches/iter_B2c_web_google_bridge.py

YaVNYY MOST: c=a+b — podklyuchaem vneshnie fakty kak protseduru (b), ne podmenyaya “ya”.
SKRYTYE MOSTY:
  - Cover&Thomas: limity kanala (RPM/taymaut/bayty) — chtoby set ne “sela” sistemu.
  - Ashby: requisite variety — Google CSE + DDG dayut raznoobrazie istochnikov.
ZEMNOY ABZATs:
  Eto kak postavit predokhranitel i filtr pered nasosom: potok idet, no motor ne gorit, a gryaz ne letit v klapana.

Chto delaet patch:
1) Dobavlyaet bridges/internet_access.py (obertka nad vashim Google CSE stekom + DDG fallback).
2) Pravit run_ester_fixed.py:
   - WEB_AVAILABLE uchityvaet Google CSE klyuchi/bridge, a ne tolko duckduckgo_search.
   - get_web_evidence() khodit cherez InternetAccess.
   - need_web_search_llm() imeet bystryy evristicheskiy trigger po URL/«zagolovki/novosti».

Avto-otkat:
- Esli kompilyatsiya padaet, run_ester_fixed.py otkatyvaetsya na bekap.

Zapusk:
PS> cd D:\ester-project
PS> python tools\patches\iter_B2c_web_google_bridge.py
"""

from __future__ import annotations

import os
import re
import shutil
import time
import py_compile
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def _write(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def _backup(p: Path, tag: str) -> Path:
    b = p.with_name(p.name + f".bak_{tag}_{_now_tag()}")
    shutil.copy2(str(p), str(b))
    return b


def _find_root() -> Path:
    here = Path(__file__).resolve()
    for cand in [here.parents[2], here.parents[1], Path.cwd()]:
        if (cand / "run_ester_fixed.py").exists():
            return cand
    return Path.cwd()


ROOT = _find_root()
RUN = ROOT / "run_ester_fixed.py"
BRIDGE = ROOT / "bridges" / "internet_access.py"

if not RUN.exists():
    raise SystemExit(f"Missing: {RUN}")

tag = "B2c"
b_run = _backup(RUN, tag)

bridge_code = '# -*- coding: utf-8 -*-\n"""\nbridges/internet_access.py — setevoy most Ester (poisk + bezopasnaya vyborochnaya zagruzka HTML).\n\nYaVNYY MOST: c=a+b — vneshniy fakt podtyagivaem protseduroy (b), ne lomaya subektnost “c”.\nSKRYTYE MOSTY:\n  - Cover&Thomas: ogranichenie kanala — RPM/taymaut/limit bayt, chtoby ne zabit liniyu i ne raznesti pamyat.\n  - Ashby: requisite variety — neskolko provayderov (Google CSE → DDGS → DDG API) dayut raznoobrazie, a arbitr — stabilizatsiyu.\nZEMNOY ABZATs (inzheneriya/anatomiya):\n  Eto kak postavit klapan+manometr na magistral: davlenie (zaprosy) doziruem, musor (lishnie bayty) filtruem,\n  a peregrev (flud/taymauty) gasim do togo, kak “serdtse” (event loop) nachnet aritmit.\n\nBezopasnye defolty:\n- CLOSED_BOX=1 ili WEB_FACTCHECK=never  -> set vyklyuchena polnostyu.\n- fetch_html() po umolchaniyu vyklyuchen (WEB_ALLOW_FETCH=0) i rezhet SSRF (lokalkhost/privatnye seti).\n\nENV (osnovnye):\n  WEB_FACTCHECK=auto|always|never\n  WEB_MAX_RPM=12\n  WEB_TIMEOUT_SEC=8\n  WEB_MAX_BYTES=800000\n  WEB_USER_AGENT="Ester/1.0"\n  WEB_PROVIDER=auto|google_cse|ddgs|ddg_api\n  WEB_ALLOW_FETCH=0|1\n  GOOGLE_API_KEY=...\n  GOOGLE_CSE_ID=...\n"""\n\nfrom __future__ import annotations\n\nimport json\nimport os\nimport re\nimport time\nimport threading\nimport ipaddress\nfrom dataclasses import dataclass\nfrom typing import Any, Dict, List, Optional, Tuple\nfrom urllib.parse import urlencode, urlparse\nfrom urllib.request import Request, urlopen\n\ntry:\n    from duckduckgo_search import DDGS  # type: ignore\nexcept Exception:\n    DDGS = None  # type: ignore\n\n\n@dataclass\nclass WebResult:\n    title: str\n    url: str\n    snippet: str\n    source: str = "web"\n\n\nclass _RateLimiter:\n    def __init__(self, max_per_min: int) -> None:\n        self.max_per_min = max(1, int(max_per_min or 1))\n        self._lock = threading.Lock()\n        self._ts: List[float] = []\n\n    def allow(self) -> bool:\n        now = time.time()\n        cutoff = now - 60.0\n        with self._lock:\n            self._ts = [t for t in self._ts if t >= cutoff]\n            if len(self._ts) >= self.max_per_min:\n                return False\n            self._ts.append(now)\n            return True\n\n\ndef _env_bool(name: str, default: bool = False) -> bool:\n    v = (os.getenv(name, "") or "").strip().lower()\n    if not v:\n        return bool(default)\n    return v in ("1", "true", "yes", "y", "on")\n\n\ndef _is_private_host(host: str) -> bool:\n    h = (host or "").strip().lower()\n    if not h:\n        return True\n    if h in ("localhost", "localhost."):\n        return True\n    # raw ip?\n    try:\n        ip = ipaddress.ip_address(h)\n        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast\n    except Exception:\n        pass\n    # obvious local zones\n    if h.endswith(".local") or h.endswith(".localhost") or h.endswith(".internal"):\n        return True\n    return False\n\n\nclass InternetAccess:\n    def __init__(self) -> None:\n        self.web_factcheck = (os.getenv("WEB_FACTCHECK", "auto") or "auto").strip().lower()\n        self.max_rpm = int(os.getenv("WEB_MAX_RPM", "12") or "12")\n        self.timeout = float(os.getenv("WEB_TIMEOUT_SEC", "8") or "8")\n        self.max_bytes = int(os.getenv("WEB_MAX_BYTES", "800000") or "800000")\n        self.ua = (os.getenv("WEB_USER_AGENT", "") or "").strip() or "Ester/1.0"\n        self.provider = (os.getenv("WEB_PROVIDER", "auto") or "auto").strip().lower()\n        self.allow_fetch = _env_bool("WEB_ALLOW_FETCH", False)\n        self.google_api_key = (os.getenv("GOOGLE_API_KEY", "") or "").strip()\n        self.google_cse_id = (os.getenv("GOOGLE_CSE_ID", "") or "").strip()\n        self._rl = _RateLimiter(self.max_rpm)\n\n    def enabled(self) -> bool:\n        if _env_bool("CLOSED_BOX", False):\n            return False\n        if self.web_factcheck == "never":\n            return False\n        return True\n\n    def google_configured(self) -> bool:\n        return bool(self.google_api_key and self.google_cse_id)\n\n    # ---------- low-level ----------\n    def _http_get(self, url: str, accept: str = "*/*") -> Optional[bytes]:\n        if not self._rl.allow():\n            return None\n        try:\n            req = Request(url, headers={"User-Agent": self.ua, "Accept": accept})\n            with urlopen(req, timeout=self.timeout) as resp:\n                data = resp.read(self.max_bytes + 1)\n            if len(data) > self.max_bytes:\n                return data[: self.max_bytes]\n            return data\n        except Exception:\n            return None\n\n    def _http_get_json(self, url: str) -> Optional[Dict[str, Any]]:\n        raw = self._http_get(url, accept="application/json")\n        if not raw:\n            return None\n        try:\n            return json.loads(raw.decode("utf-8", errors="ignore"))\n        except Exception:\n            return None\n\n    # ---------- search providers ----------\n    def _search_google_cse_urllib(self, query: str, max_results: int) -> List[WebResult]:\n        if not self.google_configured():\n            return []\n        params = {\n            "key": self.google_api_key,\n            "cx": self.google_cse_id,\n            "q": query,\n            "num": str(max(1, min(10, int(max_results)))),\n            "safe": "off",\n        }\n        url = "https://www.googleapis.com/customsearch/v1?" + urlencode(params)\n        j = self._http_get_json(url)\n        if not j:\n            return []\n        items = j.get("items") or []\n        out: List[WebResult] = []\n        for it in items:\n            try:\n                title = str(it.get("title") or "").strip()\n                link = str(it.get("link") or "").strip()\n                snippet = str(it.get("snippet") or "").strip()\n                if not (title or snippet):\n                    continue\n                out.append(WebResult(title=title, url=link, snippet=snippet, source="google_cse"))\n                if len(out) >= max_results:\n                    break\n            except Exception:\n                continue\n        return out\n\n    def _search_google_via_existing_bridge(self, query: str, max_results: int) -> List[WebResult]:\n        # 1) engines.google_search_bridge.search\n        try:\n            from engines.google_search_bridge import search as gsearch  # type: ignore\n            payload = gsearch(query=query, limit=int(max_results), source="telegram", autonomy={"ester": True})\n            if isinstance(payload, dict) and payload.get("ok") and payload.get("items"):\n                out: List[WebResult] = []\n                for it in payload.get("items") or []:\n                    title = str(it.get("title") or "").strip()\n                    url = str(it.get("link") or it.get("url") or "").strip()\n                    snippet = str(it.get("snippet") or it.get("body") or "").strip()\n                    if not (title or snippet):\n                        continue\n                    out.append(WebResult(title=title, url=url, snippet=snippet, source="google_bridge"))\n                    if len(out) >= max_results:\n                        break\n                return out\n        except Exception:\n            pass\n\n        # 2) modules.providers.google_cse_adapter.GoogleCSEAdapter\n        try:\n            from modules.providers.google_cse_adapter import GoogleCSEAdapter  # type: ignore\n            ad = GoogleCSEAdapter()\n            payload = ad.search(query=query, limit=int(max_results), source="telegram", autonomy={"ester": True})\n            if isinstance(payload, dict) and payload.get("ok") and payload.get("items"):\n                out: List[WebResult] = []\n                for it in payload.get("items") or []:\n                    title = str(it.get("title") or "").strip()\n                    url = str(it.get("link") or it.get("url") or "").strip()\n                    snippet = str(it.get("snippet") or it.get("body") or "").strip()\n                    if not (title or snippet):\n                        continue\n                    out.append(WebResult(title=title, url=url, snippet=snippet, source="google_adapter"))\n                    if len(out) >= max_results:\n                        break\n                return out\n        except Exception:\n            pass\n\n        return []\n\n    def _search_ddgs(self, query: str, max_results: int) -> List[WebResult]:\n        if DDGS is None:\n            return []\n        try:\n            if not self._rl.allow():\n                return []\n            out: List[WebResult] = []\n            with DDGS() as ddgs:\n                for r in ddgs.text(query, max_results=int(max_results)):\n                    title = str(r.get("title") or "").strip()\n                    snippet = str(r.get("body") or "").strip()\n                    url = str(r.get("href") or "").strip()\n                    if not (title or snippet):\n                        continue\n                    out.append(WebResult(title=title, url=url, snippet=snippet, source="ddgs"))\n                    if len(out) >= max_results:\n                        break\n            return out\n        except Exception:\n            return []\n\n    def _search_ddg_api(self, query: str, max_results: int) -> List[WebResult]:\n        params = {\n            "q": query,\n            "format": "json",\n            "no_redirect": "1",\n            "no_html": "1",\n            "skip_disambig": "1",\n        }\n        url = "https://api.duckduckgo.com/?" + urlencode(params)\n        j = self._http_get_json(url)\n        if not j:\n            return []\n        out: List[WebResult] = []\n        abs_txt = str(j.get("AbstractText") or "").strip()\n        abs_url = str(j.get("AbstractURL") or "").strip()\n        heading = str(j.get("Heading") or "").strip()\n        if abs_txt:\n            out.append(WebResult(title=heading or "DuckDuckGo", url=abs_url, snippet=abs_txt, source="ddg_api"))\n\n        def _take_topics(x: Any) -> None:\n            if isinstance(x, list):\n                for it in x:\n                    _take_topics(it)\n            elif isinstance(x, dict):\n                if "Topics" in x:\n                    _take_topics(x.get("Topics"))\n                    return\n                txt = str(x.get("Text") or "").strip()\n                first = str(x.get("FirstURL") or "").strip()\n                if txt:\n                    out.append(WebResult(title=txt[:80], url=first, snippet=txt, source="ddg_api"))\n\n        _take_topics(j.get("RelatedTopics"))\n\n        uniq: List[WebResult] = []\n        seen = set()\n        for r in out:\n            key = (r.title, r.snippet)\n            if key in seen:\n                continue\n            seen.add(key)\n            uniq.append(r)\n            if len(uniq) >= max_results:\n                break\n        return uniq\n\n    # ---------- public API ----------\n    def search(self, query: str, max_results: int = 5) -> List[WebResult]:\n        if not self.enabled():\n            return []\n        q = (query or "").strip()\n        if not q:\n            return []\n        max_results = max(1, min(10, int(max_results or 5)))\n\n        # provider order\n        prov = self.provider\n        if prov not in ("auto", "google_cse", "ddgs", "ddg_api"):\n            prov = "auto"\n\n        def _uniq(rs: List[WebResult]) -> List[WebResult]:\n            out: List[WebResult] = []\n            seen = set()\n            for r in rs:\n                k = (r.title, r.url)\n                if k in seen:\n                    continue\n                seen.add(k)\n                out.append(r)\n                if len(out) >= max_results:\n                    break\n            return out\n\n        # 1) google via existing bridges/adapters (preferred if configured)\n        if prov in ("auto", "google_cse"):\n            rs = self._search_google_via_existing_bridge(q, max_results)\n            if rs:\n                return _uniq(rs)\n            rs = self._search_google_cse_urllib(q, max_results)\n            if rs:\n                return _uniq(rs)\n\n        # 2) ddgs\n        if prov in ("auto", "ddgs"):\n            rs = self._search_ddgs(q, max_results)\n            if rs:\n                return _uniq(rs)\n\n        # 3) ddg api\n        rs = self._search_ddg_api(q, max_results)\n        return _uniq(rs)\n\n    def fetch_html(self, url: str) -> str:\n        """Optsionalno: gruzim HTML stranitsy (tolko esli WEB_ALLOW_FETCH=1)."""\n        if not self.enabled() or not self.allow_fetch:\n            return ""\n        u = (url or "").strip()\n        if not u:\n            return ""\n        try:\n            p = urlparse(u)\n            if p.scheme not in ("http", "https"):\n                return ""\n            host = p.hostname or ""\n            if _is_private_host(host):\n                return ""\n        except Exception:\n            return ""\n        raw = self._http_get(u, accept="text/html,application/xhtml+xml")\n        if not raw:\n            return ""\n        try:\n            return raw.decode("utf-8", errors="ignore")\n        except Exception:\n            return ""\n\n    def extract_headlines(self, url: str, limit: int = 12) -> List[str]:\n        html = self.fetch_html(url)\n        if not html:\n            return []\n        limit = max(1, min(40, int(limit or 12)))\n\n        # grubyy, no bystryy HTML text extraction dlya <a> i <h*>:\n        # vynimaem tekst, chistim, filtruem musor.\n        candidates: List[str] = []\n\n        # h1-h4\n        for m in re.finditer(r"<(h[1-4])[^>]*>(.*?)</\\1>", html, flags=re.I | re.S):\n            t = re.sub(r"<[^>]+>", " ", m.group(2))\n            t = re.sub(r"\\s+", " ", t).strip()\n            if 25 <= len(t) <= 140:\n                candidates.append(t)\n\n        # links\n        for m in re.finditer(r"<a[^>]+>(.*?)</a>", html, flags=re.I | re.S):\n            t = re.sub(r"<[^>]+>", " ", m.group(1))\n            t = re.sub(r"\\s+", " ", t).strip()\n            if 25 <= len(t) <= 140:\n                candidates.append(t)\n\n        # drop obvious UI words\n        bad = ("vkhod", "registratsiya", "podpis", "menyu", "poisk", "glavnaya", "kontak", "cookie")\n        out: List[str] = []\n        seen = set()\n        for t in candidates:\n            lo = t.lower()\n            if any(b in lo for b in bad):\n                continue\n            if t in seen:\n                continue\n            seen.add(t)\n            out.append(t)\n            if len(out) >= limit:\n                break\n        return out\n\n    @staticmethod\n    def format_evidence(results: List[WebResult], max_chars: int = 1800) -> str:\n        max_chars = max(200, int(max_chars or 1800))\n        if not results:\n            return ""\n        lines: List[str] = []\n        for r in results:\n            t = (r.title or "").strip()\n            s = (r.snippet or "").strip()\n            u = (r.url or "").strip()\n            row = f"- {t}: {s}"\n            if u:\n                row += f" ({u})"\n            lines.append(row)\n        txt = "\\n".join(lines).strip()\n        if len(txt) > max_chars:\n            txt = txt[: max_chars].rstrip() + "…"\n        return txt\n\n    @staticmethod\n    def format_headlines(headlines: List[str], url: str = "", max_chars: int = 1800) -> str:\n        max_chars = max(200, int(max_chars or 1800))\n        if not headlines:\n            return ""\n        lines = [f"- {h}" for h in headlines]\n        if url:\n            lines.append(f"(Istochnik: {url})")\n        txt = "\\n".join(lines).strip()\n        if len(txt) > max_chars:\n            txt = txt[: max_chars].rstrip() + "…"\n        return txt\n'
_write(BRIDGE, bridge_code)

src = _read(RUN)

# --- patch 1: optional web block ---
new_web_block = r'''# --- 2) OPTIONAL: web search (Google CSE / NetBridge / DDG) ---
# Uses existing project infrastructure when available (Google CSE keys in .env),
# and falls back to DDG providers.
try:
    from bridges.internet_access import InternetAccess  # type: ignore
except Exception:
    InternetAccess = None  # type: ignore

try:
    from duckduckgo_search import DDGS  # type: ignore
except Exception:
    DDGS = None  # type: ignore

_GOOGLE_OK = bool((os.getenv("GOOGLE_API_KEY", "") or "").strip() and (os.getenv("GOOGLE_CSE_ID", "") or "").strip())
WEB_AVAILABLE = bool(_GOOGLE_OK or (InternetAccess is not None) or (DDGS is not None))

'''

pat_web = re.compile(
    r"^#\s*---\s*2\)\s*OPTIONAL:\s*web\s*search\s*\(DDG\)\s*---\s*\n.*?\n(?=^#\s*---\s*3\)\s*Telegram)",
    re.M | re.S,
)
if not pat_web.search(src):
    shutil.copy2(str(b_run), str(RUN))
    raise SystemExit("B2c: cannot find optional web search block (pattern mismatch).")
src = pat_web.sub(new_web_block, src, count=1)

# --- patch 2: replace get_web_evidence() body ---
i1 = src.find("def get_web_evidence")
i2 = src.find("async def get_web_evidence_async")
if i1 < 0 or i2 < 0 or i2 <= i1:
    shutil.copy2(str(b_run), str(RUN))
    raise SystemExit("B2c: cannot locate get_web_evidence / get_web_evidence_async.")

new_get = r'''def get_web_evidence(query: str, max_results: int = 3) -> str:
    """
    Web facts for cascade (sync).

    Uses project infrastructure first:
      - bridges.internet_access.InternetAccess (Google CSE / adapters / DDG fallbacks)

    Respects:
      - CLOSED_BOX=1  -> disabled
      - WEB_FACTCHECK=never -> disabled
    """
    try:
        if CLOSED_BOX:
            return ""
    except Exception:
        pass
    try:
        if str(WEB_FACTCHECK).strip().lower() == "never":
            return ""
    except Exception:
        pass
    if not WEB_AVAILABLE:
        return ""

    q = (query or "").strip()
    if not q:
        return ""

    # If user gave an URL — try:
    # 1) headlines from HTML (optional, env-gated),
    # 2) then search with site:<host> … (better than raw long sentence).
    try:
        qlow = q.lower()
        urlm = re.search(r"(https?://\S+)", q)
        if urlm:
            url0 = urlm.group(1)

            # 1) headlines (only if WEB_ALLOW_FETCH=1)
            if any(k in qlow for k in ("zagolov", "headlines", "headline", "novost")):
                try:
                    from bridges.internet_access import InternetAccess  # type: ignore
                    ia = InternetAccess()
                    heads = ia.extract_headlines(url0, limit=max(8, int(max_results) * 4))
                    if heads:
                        return ia.format_headlines(heads, url=url0, max_chars=int(MAX_WEB_CHARS)).strip()
                except Exception:
                    pass

            # 2) site:host query rewrite
            try:
                import urllib.parse as _up
                host = (_up.urlparse(url0).hostname or "").strip()
                if host:
                    rest = re.sub(r"https?://\S+", " ", q).strip()
                    rest = re.sub(r"\s+", " ", rest).strip()
                    if rest:
                        q = f"site:{host} {rest}"
                    else:
                        q = f"site:{host} novosti"
            except Exception:
                pass
    except Exception:
        pass

    # Normal web evidence (search)
    try:
        from bridges.internet_access import InternetAccess  # type: ignore
        ia = InternetAccess()
        res = ia.search(q, max_results=int(max_results or 3))
        txt = ia.format_evidence(res, max_chars=int(MAX_WEB_CHARS))
        return (txt or "").strip()
    except Exception:
        pass

    # Last resort: legacy DDGS (if installed)
    try:
        if "DDGS" in globals() and DDGS:
            out = []
            with DDGS() as ddgs:
                for r in ddgs.text(q, max_results=int(max_results or 3)):
                    title = (r.get("title") or "").strip()
                    body = (r.get("body") or "").strip()
                    href = (r.get("href") or "").strip()
                    if not (title or body):
                        continue
                    row = f"- {title}: {body}"
                    if href:
                        row += f" ({href})"
                    out.append(row)
            return truncate_text("\n".join(out).strip(), int(MAX_WEB_CHARS))
    except Exception:
        return ""

    return ""
'''
src = src[:i1] + new_get + "\n\n" + src[i2:]

# --- patch 3: need_web_search_llm() heuristic fast-path ---
lines = src.splitlines()
try:
    s = next(i for i, ln in enumerate(lines) if ln.startswith("async def need_web_search_llm"))
except StopIteration:
    shutil.copy2(str(b_run), str(RUN))
    raise SystemExit("B2c: cannot find need_web_search_llm()")

e = None
for j in range(s + 1, len(lines)):
    if lines[j] and not lines[j].startswith(" "):
        e = j
        break
if e is None:
    shutil.copy2(str(b_run), str(RUN))
    raise SystemExit("B2c: cannot determine need_web_search_llm() end")

new_func = r'''async def need_web_search_llm(decider_provider: str, user_text: str) -> bool:
    if WEB_FACTCHECK == "never":
        return False
    if WEB_FACTCHECK == "always":
        return True
    if CLOSED_BOX:
        return False

    # Heuristic fast-path: esli chelovek yavno prosit "posmotret/proverit/zagolovki" ili daet URL — ischem.
    t0 = (user_text or "").strip().lower()
    if ("http://" in t0) or ("https://" in t0):
        return True
    if any(k in t0 for k in ("zagolov", "headlines", "headline", "novost", "segodnya", "posmotri", "prover", "naydi", "chto tam")):
        return True

    sys_prompt = "Need internet search? Answer only: YES or NO."
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": truncate_text(user_text, 4000)},
    ]
    txt = await _safe_chat(decider_provider, msgs, temperature=0.0, max_tokens=16)
    t = (txt or "").strip().upper()
    if "YES" in t:
        return True
    if "NO" in t:
        return False
    return True
'''
new_lines = lines[:s] + new_func.splitlines() + lines[e:]
src = "\n".join(new_lines) + ("\n" if not src.endswith("\n") else "")

_write(RUN, src)

# compile smoke + rollback
try:
    py_compile.compile(str(BRIDGE), doraise=True)
    py_compile.compile(str(RUN), doraise=True)
except Exception as e:
    shutil.copy2(str(b_run), str(RUN))
    raise SystemExit(f"B2c failed, rolled back run_ester_fixed.py: {e}")

print("[OK] ITER B2c patched.")
print("  Backup:", b_run.name)
print("  Added :", str(BRIDGE.relative_to(ROOT)))
print("NOTE: restart run_ester_fixed.py to load changes.")