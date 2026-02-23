# -*- coding: utf-8 -*-
"""
bridges/web_browser.py — polnotsennyy veb-brauzer dlya Ester.

PROBLEMA REShENA:
Ester govorila "dostup ogranichen" potomu chto u nee byl tolko POISK (ssylki),
no ne bylo ChTENIYa (soderzhimoe stranits). Etot modul daet polnyy dostup.

API:
  • browse(url) → WebPage — otkryt URL i poluchit kontent
  • search_and_read(query, k=3) → List[WebPage] — poisk + chtenie top-k stranits
  • extract_text(html) → str — izvlech chistyy tekst iz HTML
  • extract_links(html, base_url) → List[str] — izvlech vse ssylki

Rezhimy (WEB_BROWSER_MODE):
  • "light"  — tolko urllib + readability (po umolchaniyu, bystryy)
  • "medium" — requests-html s chastichnym JS
  • "full"   — Playwright dlya slozhnykh sluchaev (trebuet ustanovki)

Mosty:
- Yavnyy: (Poisk ↔ Chtenie) — search_and_read obedinyaet oba deystviya v odnu operatsiyu.
- Skrytyy #1: (Infoteoriya ↔ Szhatie) — readability ubiraet shum, ostavlyaya sut.
- Skrytyy #2: (Kibernetika ↔ Obratnaya svyaz) — fallback mezhdu rezhimami pri oshibkakh.

Zemnoy abzats:
Predstav veb-stranitsu kak zhivuyu tkan: HTML — eto skelet (kosti), CSS — kozha,
JavaScript — myshtsy i nervy. Obychnyy urllib vidit tolko skelet. Readability
umeet otdelyat "myaso" (poleznyy tekst) ot "zhira" (reklama, navigatsiya).
Playwright — eto polnotsennoe vskrytie s rabotayuschimi organami.

Ester poluchaet sposobnost ne prosto nakhodit istochniki, no i chitat ikh
soderzhimoe — kak chelovek pered brauzerom.

# c=a+b
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

logger = logging.getLogger("ester.bridges.web_browser")

# === Konfiguratsiya ===

WEB_BROWSER_ENABLED = os.getenv("WEB_BROWSER_ENABLED", "1") == "1"
WEB_BROWSER_MODE = (os.getenv("WEB_BROWSER_MODE", "light") or "light").strip().lower()
WEB_BROWSER_TIMEOUT = float(os.getenv("WEB_BROWSER_TIMEOUT_SEC", "15"))
WEB_BROWSER_MAX_BYTES = int(os.getenv("WEB_BROWSER_MAX_BYTES", "2000000"))  # 2MB
WEB_BROWSER_MAX_PAGES = int(os.getenv("WEB_BROWSER_MAX_PAGES_PER_QUERY", "5"))
WEB_BROWSER_CACHE_TTL = int(os.getenv("WEB_BROWSER_CACHE_TTL_SEC", "600"))  # 10 min
WEB_BROWSER_USER_AGENT = os.getenv(
    "WEB_BROWSER_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Ester/2.0"
)

# Blokiruem opasnye domeny
BLOCKED_DOMAINS = {
    d.strip().lower()
    for d in (os.getenv("WEB_BROWSER_BLOCKED_DOMAINS", "") or "").split(",")
    if d.strip()
}

# === Struktury dannykh ===


@dataclass
class WebPage:
    """Rezultat otkrytiya veb-stranitsy."""
    url: str
    title: str = ""
    text: str = ""
    html: str = ""
    links: List[str] = field(default_factory=list)
    meta_description: str = ""
    status: int = 0
    error: str = ""
    fetch_time_ms: float = 0
    mode_used: str = "light"
    from_cache: bool = False

    def ok(self) -> bool:
        return self.status == 200 and not self.error

    def summary(self, max_chars: int = 500) -> str:
        """Kratkoe soderzhanie stranitsy."""
        text = self.text[:max_chars]
        if len(self.text) > max_chars:
            text += "..."
        return f"[{self.title}]\n{text}"


# === Kesh ===


class _PageCache:
    """Prostoy TTL-kesh dlya stranits."""

    def __init__(self, ttl_sec: int = 600):
        self.ttl = ttl_sec
        self._store: Dict[str, Tuple[float, WebPage]] = {}
        self._lock = threading.Lock()

    def _key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def get(self, url: str) -> Optional[WebPage]:
        k = self._key(url)
        with self._lock:
            item = self._store.get(k)
            if not item:
                return None
            exp, page = item
            if time.time() > exp:
                del self._store[k]
                return None
            page.from_cache = True
            return page

    def put(self, url: str, page: WebPage) -> None:
        k = self._key(url)
        with self._lock:
            self._store[k] = (time.time() + self.ttl, page)

    def clear(self) -> int:
        with self._lock:
            n = len(self._store)
            self._store.clear()
            return n


_cache = _PageCache(WEB_BROWSER_CACHE_TTL)


# === HTML parsing ===


class _ReadabilityParser(HTMLParser):
    """
    Uproschennyy readability-parser: izvlekaet tekst, ignoriruya skripty,
    stili, navigatsiyu i reklamu.
    """

    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "iframe", "svg"}
    BLOCK_TAGS = {"p", "div", "article", "section", "main", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "blockquote"}

    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.text_parts: List[str] = []
        self.links: List[str] = []
        self._in_title = False
        self._skip_depth = 0
        self._tag_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)

        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

        if tag == "title":
            self._in_title = True

        if tag == "meta":
            d = dict(attrs)
            name = (d.get("name") or "").lower()
            if name == "description" and not self.description:
                self.description = d.get("content") or ""

        if tag == "a":
            href = dict(attrs).get("href")
            if href and href.startswith(("http://", "https://")):
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

        if tag == "title":
            self._in_title = False

        # Dobavlyaem perevod stroki posle blochnykh elementov
        if tag in self.BLOCK_TAGS and self.text_parts:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return

        text = data.strip()
        if not text:
            return

        if self._in_title:
            self.title += text
        else:
            self.text_parts.append(text + " ")

    def get_text(self) -> str:
        raw = "".join(self.text_parts)
        # Normalizuem probely
        text = re.sub(r"[ \t]+", " ", raw)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()


def extract_text(html: str) -> Tuple[str, str, str, List[str]]:
    """
    Izvlekaet tekst iz HTML.
    Vozvraschaet: (title, description, text, links)
    """
    parser = _ReadabilityParser()
    try:
        parser.feed(html)
    except Exception as e:
        logger.warning(f"HTML parse error: {e}")
    return parser.title.strip(), parser.description.strip(), parser.get_text(), parser.links


# === HTTP klient ===


def _is_blocked(url: str) -> bool:
    """Proveryaet, zablokirovan li domen."""
    try:
        host = urlparse(url).hostname or ""
        host = host.lower()
        if host in BLOCKED_DOMAINS:
            return True
        # Proveryaem poddomeny
        for blocked in BLOCKED_DOMAINS:
            if host.endswith("." + blocked):
                return True
    except Exception:
        pass
    return False


def _fetch_light(url: str) -> WebPage:
    """Legkiy rezhim: urllib bez JS."""
    t0 = time.time()
    page = WebPage(url=url, mode_used="light")

    try:
        req = Request(url, headers={
            "User-Agent": WEB_BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            "Accept-Encoding": "identity",  # Bez szhatiya dlya prostoty
        })
        with urlopen(req, timeout=WEB_BROWSER_TIMEOUT) as resp:
            page.status = resp.status
            content_type = resp.headers.get("Content-Type", "")

            # Proveryaem chto eto HTML
            if "text/html" not in content_type.lower() and "application/xhtml" not in content_type.lower():
                page.error = f"Not HTML: {content_type}"
                return page

            raw = resp.read(WEB_BROWSER_MAX_BYTES)

        # Dekodiruem
        html = ""
        for enc in ["utf-8", "cp1251", "latin-1"]:
            try:
                html = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        page.html = html
        page.title, page.meta_description, page.text, page.links = extract_text(html)

    except Exception as e:
        page.error = str(e)
        page.status = 0

    page.fetch_time_ms = (time.time() - t0) * 1000
    return page


def _fetch_medium(url: str) -> WebPage:
    """Sredniy rezhim: requests-html s chastichnym JS (esli dostupen)."""
    try:
        from requests_html import HTMLSession
        session = HTMLSession()

        t0 = time.time()
        page = WebPage(url=url, mode_used="medium")

        try:
            resp = session.get(url, timeout=WEB_BROWSER_TIMEOUT, headers={
                "User-Agent": WEB_BROWSER_USER_AGENT
            })
            page.status = resp.status_code

            # Renderim JS (esli nuzhno)
            try:
                resp.html.render(timeout=10, sleep=1)
            except Exception:
                pass  # Fallback na staticheskiy HTML

            page.html = resp.html.html
            page.text = resp.html.text
            page.title = resp.html.find("title", first=True)
            if page.title:
                page.title = page.title.text
            else:
                page.title = ""

            # Ssylki
            page.links = [a for a in resp.html.absolute_links if a.startswith("http")]

        except Exception as e:
            page.error = str(e)

        page.fetch_time_ms = (time.time() - t0) * 1000
        return page

    except ImportError:
        logger.warning("requests-html not installed, falling back to light mode")
        return _fetch_light(url)


def _fetch_full(url: str) -> WebPage:
    """Polnyy rezhim: Playwright (headless Chrome)."""
    try:
        from playwright.sync_api import sync_playwright

        t0 = time.time()
        page = WebPage(url=url, mode_used="full")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=WEB_BROWSER_USER_AGENT,
                    viewport={"width": 1920, "height": 1080}
                )
                pw_page = context.new_page()
                pw_page.goto(url, timeout=int(WEB_BROWSER_TIMEOUT * 1000))
                pw_page.wait_for_load_state("domcontentloaded")

                page.status = 200  # Playwright ne daet status napryamuyu
                page.html = pw_page.content()
                page.title = pw_page.title()
                page.text = pw_page.inner_text("body")

                # Ssylki
                links = pw_page.eval_on_selector_all(
                    "a[href]",
                    "els => els.map(e => e.href).filter(h => h.startsWith('http'))"
                )
                page.links = links[:100]  # Limit

                browser.close()

        except Exception as e:
            page.error = str(e)

        page.fetch_time_ms = (time.time() - t0) * 1000
        return page

    except ImportError:
        logger.warning("playwright not installed, falling back to light mode")
        return _fetch_light(url)


# === Publichnyy API ===


def browse(url: str, mode: Optional[str] = None, use_cache: bool = True) -> WebPage:
    """
    Otkryvaet URL i vozvraschaet soderzhimoe stranitsy.

    Args:
        url: URL dlya otkrytiya
        mode: Rezhim ("light", "medium", "full"). Po umolchaniyu iz ENV.
        use_cache: Ispolzovat kesh

    Returns:
        WebPage s rezultatom
    """
    if not WEB_BROWSER_ENABLED:
        return WebPage(url=url, error="Web browser disabled (WEB_BROWSER_ENABLED=0)")

    if _is_blocked(url):
        return WebPage(url=url, error="Domain blocked")

    # Kesh
    if use_cache:
        cached = _cache.get(url)
        if cached:
            return cached

    # Vybiraem rezhim
    mode = (mode or WEB_BROWSER_MODE).lower()

    if mode == "full":
        page = _fetch_full(url)
    elif mode == "medium":
        page = _fetch_medium(url)
    else:
        page = _fetch_light(url)

    # Fallback pri oshibke
    if not page.ok() and mode != "light":
        logger.info(f"Fallback to light mode for {url}")
        page = _fetch_light(url)

    # Keshiruem uspeshnye
    if page.ok() and use_cache:
        _cache.put(url, page)

    return page


def search_and_read(
    query: str,
    k: int = 3,
    mode: Optional[str] = None,
    search_provider: Optional[str] = None
) -> List[WebPage]:
    """
    Vypolnyaet poisk i chitaet soderzhimoe top-k stranits.

    Args:
        query: Poiskovyy zapros
        k: Skolko stranits prochitat (maks. WEB_BROWSER_MAX_PAGES)
        mode: Rezhim brauzera
        search_provider: Provayder poiska (po umolchaniyu iz modules/web_search)

    Returns:
        Spisok WebPage s rezultatami
    """
    k = max(1, min(k, WEB_BROWSER_MAX_PAGES))

    # Importiruem poisk
    try:
        from modules.web_search import search_web
    except ImportError:
        logger.error("modules.web_search not found")
        return []

    # Poisk
    hits = search_web(query, topk=k * 2)  # Berem s zapasom
    if not hits:
        return []

    # Chitaem stranitsy
    pages: List[WebPage] = []
    for hit in hits:
        if len(pages) >= k:
            break
        url = hit.get("url")
        if not url:
            continue
        page = browse(url, mode=mode)
        if page.ok():
            pages.append(page)

    return pages


def read_urls(urls: List[str], mode: Optional[str] = None) -> List[WebPage]:
    """
    Chitaet spisok URL parallelno (poka posledovatelno dlya prostoty).
    """
    pages: List[WebPage] = []
    for url in urls[:WEB_BROWSER_MAX_PAGES]:
        pages.append(browse(url, mode=mode))
    return pages


def clear_cache() -> int:
    """Ochischaet kesh, vozvraschaet kolichestvo udalennykh zapisey."""
    return _cache.clear()


# === Statistika ===


_stats = {
    "browse_calls": 0,
    "cache_hits": 0,
    "errors": 0,
    "total_bytes": 0,
}


def stats() -> Dict[str, Any]:
    """Vozvraschaet statistiku ispolzovaniya."""
    return dict(_stats)


# === CLI dlya testirovaniya ===


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python web_browser.py <url> [mode]")
        print("Modes: light, medium, full")
        sys.exit(1)

    url = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "light"

    print(f"Browsing: {url}")
    print(f"Mode: {mode}")
    print("-" * 60)

    page = browse(url, mode=mode)

    print(f"Status: {page.status}")
    print(f"Title: {page.title}")
    print(f"Description: {page.meta_description}")
    print(f"Text length: {len(page.text)} chars")
    print(f"Links: {len(page.links)}")
    print(f"Time: {page.fetch_time_ms:.0f}ms")
    print(f"Error: {page.error or 'None'}")
    print("-" * 60)
    print("Text preview (first 1000 chars):")
    print(page.text[:1000])

# c=a+b