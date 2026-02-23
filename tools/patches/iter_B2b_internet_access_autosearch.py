# -*- coding: utf-8 -*-
"""
ITER B2b — bridges/internet_access.py + integratsiya v kaskad (samostoyatelnye poiski)

YaVNYY MOST: c=a+b — vneshniy fakt podtyagivaem protseduroy (b), ne lomaya “ya”.
SKRYTYE MOSTY:
  - Cover&Thomas: ogranichenie kanala — RPM/taymaut/limit bayt, chtoby ne “zabit liniyu”.
  - Ashby: requisite variety — dva rezhima: DDGS (esli est) i DDG Instant Answer API (bez klyuchey).
ZEMNOY ABZATs:
  Eto kak postavit reduktor i filtr na vodu: potok est, no truby ne rvet i gryaz ne letit v sistemu.

Chto menyaem:
1) Dobavlyaem bridges/internet_access.py (stdlib-only).
2) V run_ester_fixed.py:
   - WEB_AVAILABLE teper True, esli dostupen bridges.internet_access (ili staryy DDGS).
   - get_web_evidence() ispolzuet InternetAccess; DDGS ostaetsya zapasnym.

Nikakikh “samoperenosov dannykh”. Tolko kod.
"""

from __future__ import annotations

import os, re, time, shutil, py_compile
from pathlib import Path

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
    # Nadezhno ischem koren proekta (gde lezhit run_ester_fixed.py)
    here = Path(__file__).resolve()
    for cand in [here.parents[2], here.parents[1], Path.cwd()]:
        if (cand / "run_ester_fixed.py").exists():
            return cand
    # fallback
    return Path.cwd()

ROOT = _find_root()
RUN  = ROOT / "run_ester_fixed.py"
BRIDGE = ROOT / "bridges" / "internet_access.py"

if not RUN.exists():
    raise SystemExit(f"Missing: {RUN}")

tag = "B2b"
b_run = _backup(RUN, tag)

bridge_code = r'''# -*- coding: utf-8 -*-
"""
bridges/internet_access.py — bezopasnyy most v internet (poisk/fakty).

YaVNYY MOST: c=a+b — “vneshnie fakty” podklyuchaem kak protseduru b.
SKRYTYE MOSTY:
  - Cover&Thomas: limity kanala/oshibok (RPM/bayty/taymaut).
  - Ashby: raznoobrazie istochnikov (DDGS ili DDG Instant Answer API).
ZEMNOY ABZATs:
  Kak klapan+manometr: davlenie derzhim, utechki/peregrev ne dopuskaem.

Po umolchaniyu:
- Nikakikh proizvolnykh fetch po URL (SSRF-klass problem) — tolko poisk.
- Set vyklyuchaetsya globalno cherez CLOSED_BOX=1 ili WEB_FACTCHECK=never.
"""

from __future__ import annotations

import json
import os
import time
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
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
    source: str = "ddg"


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


class InternetAccess:
    """
    Poisk faktov (bez klyuchey):
    - Prefer: duckduckgo_search.DDGS (esli ustanovlen)
    - Fallback: DuckDuckGo Instant Answer API (api.duckduckgo.com)

    ENV:
      WEB_MAX_RPM=12
      WEB_TIMEOUT_SEC=8
      WEB_DDG_MAX_RESULTS=5
      WEB_USER_AGENT="Ester/1.0 (+https://localhost)"
      WEB_PROVIDER=auto|ddgs|ddg_api
    """

    def __init__(self) -> None:
        self.max_rpm = int(os.getenv("WEB_MAX_RPM", "12") or "12")
        self.timeout = float(os.getenv("WEB_TIMEOUT_SEC", "8") or "8")
        self.ddg_max = int(os.getenv("WEB_DDG_MAX_RESULTS", "5") or "5")
        self.ua = (os.getenv("WEB_USER_AGENT", "") or "").strip() or "Ester/1.0"
        self.provider = (os.getenv("WEB_PROVIDER", "auto") or "auto").strip().lower()
        self._rl = _RateLimiter(self.max_rpm)

    def _http_get_json(self, url: str) -> Optional[Dict[str, Any]]:
        if not self._rl.allow():
            return None
        try:
            req = Request(url, headers={"User-Agent": self.ua, "Accept": "application/json"})
            with urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8", errors="ignore"))
        except Exception:
            return None

    def search(self, query: str, max_results: int = 5) -> List[WebResult]:
        q = (query or "").strip()
        if not q:
            return []

        max_results = max(1, min(10, int(max_results or 5)))

        # 1) DDGS
        if self.provider in ("auto", "ddgs") and DDGS is not None:
            try:
                if not self._rl.allow():
                    return []
                out: List[WebResult] = []
                with DDGS() as ddgs:
                    for r in ddgs.text(q, max_results=max_results):
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
                # padaem na API
                pass

        # 2) DDG Instant Answer API (bez klyucha, no rezultaty inogda “bednee”)
        if self.provider in ("auto", "ddg_api"):
            params = {
                "q": q,
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

            # abstract
            abs_txt = str(j.get("AbstractText") or "").strip()
            abs_url = str(j.get("AbstractURL") or "").strip()
            heading = str(j.get("Heading") or "").strip()
            if abs_txt:
                out.append(WebResult(title=heading or "DuckDuckGo", url=abs_url, snippet=abs_txt, source="ddg_api"))

            # related topics (mogut byt vlozhennye)
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

            # trim
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

        return []

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
'''

_write(BRIDGE, bridge_code)

src = _read(RUN)

# --- patch 1: WEB_AVAILABLE section ---
old_block_pat = re.compile(
    r"#\s*---\s*2\)\s*OPTIONAL:\s*web\s*search\s*\(DDG\)\s*---\s*.*?\n(?=\s*#\s*---\s*3\)\s*Telegram)",
    re.IGNORECASE | re.DOTALL
)

new_block = r'''# --- 2) OPTIONAL: web search (bridge) ---
# Prefer stdlib bridge (no keys). Fallback to DDGS if installed.
try:
    from bridges.internet_access import InternetAccess  # type: ignore
    WEB_AVAILABLE = True
except Exception:
    try:
        from duckduckgo_search import DDGS  # type: ignore
        WEB_AVAILABLE = True
    except Exception:
        WEB_AVAILABLE = False
        DDGS = None  # type: ignore

'''

if not old_block_pat.search(src):
    raise SystemExit("B2b: cannot find WEB_AVAILABLE DDG block to replace (pattern mismatch).")

src2 = old_block_pat.sub(new_block, src, count=1)

# --- patch 2: replace get_web_evidence() (keep async wrapper) ---
m1 = re.search(r"^def\s+get_web_evidence\s*\(.*?\):\s*$", src2, flags=re.M)
m2 = re.search(r"^async\s+def\s+get_web_evidence_async\s*\(.*?\):\s*$", src2, flags=re.M)
if not m1 or not m2 or m2.start() <= m1.start():
    raise SystemExit("B2b: cannot locate get_web_evidence / get_web_evidence_async to patch.")

start = m1.start()
end = m2.start()

new_get_web = r'''def get_web_evidence(query: str, max_results: int = 3) -> str:
    """
    Web facts for cascade (sync). Respects:
      - CLOSED_BOX=1  -> disabled
      - WEB_FACTCHECK=never -> disabled
    Uses bridges.internet_access.InternetAccess (stdlib-first).
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

    q = (query or "").strip()
    if not q:
        return ""

    # 1) stdlib bridge
    try:
        from bridges.internet_access import InternetAccess  # type: ignore
        ia = InternetAccess()
        res = ia.search(q, max_results=int(max_results or 3))
        txt = ia.format_evidence(res, max_chars=int(WEB_EVIDENCE_MAX_CHARS))
        return (txt or "").strip()
    except Exception:
        pass

    # 2) legacy DDGS fallback (if present)
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
            return truncate_text("\n".join(out).strip(), int(WEB_EVIDENCE_MAX_CHARS))
    except Exception:
        return ""

    return ""
'''

src3 = src2[:start] + new_get_web + "\n\n" + src2[end:]

_write(RUN, src3)

# compile smoke + rollback
try:
    py_compile.compile(str(BRIDGE), doraise=True)
    py_compile.compile(str(RUN), doraise=True)
except Exception as e:
    shutil.copy2(str(b_run), str(RUN))
    raise SystemExit(f"B2b failed, rolled back run_ester_fixed.py: {e}")

print("[OK] ITER B2b patched.")
print("  Backup:", b_run.name)
print("  Added :", str(BRIDGE.relative_to(ROOT)))
print("NOTE: restart run_ester_fixed.py to load changes.")