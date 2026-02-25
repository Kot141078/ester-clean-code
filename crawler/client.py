# -*- coding: utf-8 -*-
"""crawler/client.py - byudzhetirovannyy krouler s robots.txt, zapretom arkhivov i TTL-keshom.

MOSTY:
- (Yavnyy) BudgetedCrawler.fetch(url): soblyudaet OUTBOUND_MAX_RPS/OUTBOUND_BUDGET_PER_MIN, robots.txt, kesh i zapret arkhivov.
- (Skrytyy #1) Nulevye vneshnie zavisimosti: urllib/robotparser + inektsiya fetcher dlya testov/air-gap.
- (Skrytyy #2) Indeksiruet tolko metadannye (title/desc/len/links), ne tyanet tyazhelye bloby.

ZEMNOY ABZATs:
Etichnyy “nizkoprofilnyy” obkhodchik: ne shumit, uvazhaet pravila saytov i ne skachivaet lishnee.
# V prode - pod kapotom vsekh vneshnikh razborakh (reserch/onbording/integratsii). c=a+b"""
from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable, Dict, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

USER_AGENT = os.getenv("OUTBOUND_USER_AGENT", "Ester-Integrator/1.0")
MAX_RPS = float(os.getenv("OUTBOUND_MAX_RPS", "2"))
BUDGET_PER_MIN = int(os.getenv("OUTBOUND_BUDGET_PER_MIN", "60"))
CACHE_TTL = int(os.getenv("CRAWLER_CACHE_TTL_SEC", "900"))
RESPECT_ROBOTS = os.getenv("CRAWLER_RESPECT_ROBOTS", "1") == "1"
DISALLOW_ARCHIVES = os.getenv("CRAWLER_DISALLOW_ARCHIVES", "1") == "1"

_ARCHIVE_EXT = (".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".xz", ".bz2", ".apk", ".exe", ".iso")

@dataclass
class FetchResult:
    ok: bool
    url: str
    status: int
    reason: str
    title: str
    description: str
    length: int
    links: int
    cached: bool

class _TokenBucket:
    def __init__(self, rate: float, burst: Optional[float] = None):
        self.rate = max(0.1, float(rate))
        self.capacity = float(burst or rate)
        self.tokens = self.capacity
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

class _MinuteBudget:
    def __init__(self, budget: int):
        self.budget = int(budget)
        self.reset = time.time() + 60
        self.left = self.budget
        self.lock = threading.Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.time()
            if now >= self.reset:
                self.reset = now + 60
                self.left = self.budget
            if self.left <= 0:
                return False
            self.left -= 1
            return True

class _TTLCache:
    def __init__(self, ttl_sec: int):
        self.ttl = int(ttl_sec)
        self.store: Dict[str, Tuple[float, FetchResult]] = {}
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[FetchResult]:
        with self.lock:
            item = self.store.get(key)
            if not item:
                return None
            exp, val = item
            if time.time() > exp:
                del self.store[key]
                return None
            return val

    def set(self, key: str, val: FetchResult) -> None:
        with self.lock:
            self.store[key] = (time.time() + self.ttl, val)

class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ""
        self.desc = ""
        self.links = 0

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        if tag == "a":
            self.links += 1
        if tag == "meta":
            d = dict(attrs)
            if self.desc == "" and d.get("name", "").lower() == "description":
                self.desc = d.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data

class BudgetedCrawler:
    def __init__(self, fetcher: Optional[Callable[[str, Dict[str, str]], Tuple[int, bytes]]] = None):
        """fetcher(url, neaders) -> (status, content-beat)
        If not specified, orliv.registered.orlopen is used"""
        self.bucket = _TokenBucket(MAX_RPS, burst=MAX_RPS)
        self.budget = _MinuteBudget(BUDGET_PER_MIN)
        self.cache = _TTLCache(CACHE_TTL)
        self.fetcher = fetcher
        self._robots: Dict[str, urllib.robotparser.RobotFileParser] = {}

    def _is_archive(self, url: str) -> bool:
        if not DISALLOW_ARCHIVES:
            return False
        path = urllib.parse.urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in _ARCHIVE_EXT)

    def _domain(self, url: str) -> str:
        return urllib.parse.urlparse(url).netloc

    def _robots(self, url: str) -> bool:
        """Three if you can go to the URL according to robots; if it fails to read, it safely prohibits it."""
        if not RESPECT_ROBOTS:
            return True
        dom = self._domain(url)
        rp = self._robots.get(dom)
        if not rp:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{urllib.parse.urlunparse(('https','',dom,'','','/robots.txt'))}"
            try:
                rp.set_url(robots_url)
                rp.read()
            except Exception:
                # we'll ban you if it doesn't work
                self._robots[dom] = rp
                return False
            self._robots[dom] = rp
        return rp.can_fetch(USER_AGENT, url)

    def _do_fetch(self, url: str) -> Tuple[int, bytes]:
        if self.fetcher:
            return self.fetcher(url, {"User-Agent": USER_AGENT})
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as r:  # nosec - upravlyaemyy UA/taymaut
            return int(r.status), r.read(512 * 1024)  # maksimum 512 KiB

    def fetch(self, url: str) -> FetchResult:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cached = self.cache.get(key)
        if cached:
            return cached

        if self._is_archive(url):
            fr = FetchResult(False, url, 451, "disallowed_archive", "", "", 0, 0, False)
            self.cache.set(key, fr); return fr

        if not self._robots(url):
            fr = FetchResult(False, url, 451, "robots_disallow", "", "", 0, 0, False)
            self.cache.set(key, fr); return fr

        if not self.bucket.allow():
            return FetchResult(False, url, 429, "rate_limited", "", "", 0, 0, False)
        if not self.budget.allow():
            return FetchResult(False, url, 429, "budget_exceeded", "", "", 0, 0, False)

        try:
            status, content = self._do_fetch(url)
        except Exception as e:
            return FetchResult(False, url, 599, "fetch_error", "", "", 0, 0, False)

        # prostenkiy parser metadannykh
        parser = _MetaParser()
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        parser.feed(text)
        title = (parser.title or "").strip()[:200]
        desc = (parser.desc or "").strip()[:280]
        links = int(parser.links)
        fr = FetchResult(True, url, status, "ok", title, desc, len(content), links, False)
        self.cache.set(key, fr)
        return fr