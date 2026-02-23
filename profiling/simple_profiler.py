# -*- coding: utf-8 -*-
"""
profiling/simple_profiler.py — minimalistichnyy profilirovschik pod nagruzki Ester.

Funktsii:
- profile_block(path) — kontekst-menedzher cProfile -> .prof fayl + svodka pstats.
- time_http(method, url, headers=None, json=None, data=None, timeout=10) -> (status, ms)
- run_http_burst(urls, concurrency=10, duration_sec=30, headers=None) -> metriki
- CLI: python -m profiling.simple_profiler --url http://localhost:5000/backup/run --concurrency 20 --duration 30
"""
from __future__ import annotations

import argparse
import concurrent.futures
import cProfile
import io
import json
import os
import pstats
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@contextmanager
def profile_block(outfile: str):
    """
    Primer:
        with profile_block("profiles/backup_run.prof"):
            heavy_call()
    """
    os.makedirs(os.path.dirname(outfile) or ".", exist_ok=True)
    pr = cProfile.Profile()
    pr.enable()
    try:
        yield
    finally:
        pr.disable()
        pr.dump_stats(outfile)
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("tottime")
        ps.print_stats(30)
        summary_txt = outfile + ".txt"
        with open(summary_txt, "w", encoding="utf-8") as f:
            f.write(s.getvalue())


def time_http(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict] = None,
    data: Optional[Dict] = None,
    timeout: int = 10,
) -> Tuple[int, float]:
    t0 = time.perf_counter()
    try:
        r = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json,
            data=data,
            timeout=timeout,
        )
        code = r.status_code
    except requests.RequestException:
        code = -1
    ms = (time.perf_counter() - t0) * 1000.0
    return code, ms


@dataclass
class Metrics:
    total: int = 0
    ok2xx: int = 0
    auth_fail: int = 0  # 401/403
    other: int = 0
    errors: int = 0  # code < 0
    lat_sum_ms: float = 0.0
    lat_max_ms: float = 0.0
    hist: List[float] = field(default_factory=list)

    def add(self, code: int, ms: float):
        self.total += 1
        self.lat_sum_ms += ms
        self.lat_max_ms = max(self.lat_max_ms, ms)
        self.hist.append(ms)
        if code < 0:
            self.errors += 1
        elif 200 <= code < 300:
            self.ok2xx += 1
        elif code in (401, 403):
            self.auth_fail += 1
        else:
            self.other += 1

    def to_dict(self) -> Dict:
        avg = (self.lat_sum_ms / self.total) if self.total else 0.0
        p95 = percentile(self.hist, 95.0)
        p99 = percentile(self.hist, 99.0)
        return {
            "total": self.total,
            "ok2xx": self.ok2xx,
            "auth_fail": self.auth_fail,
            "other": self.other,
            "errors": self.errors,
            "lat_avg_ms": round(avg, 2),
            "lat_p95_ms": round(p95, 2),
            "lat_p99_ms": round(p99, 2),
            "lat_max_ms": round(self.lat_max_ms, 2),
        }


def percentile(samples: List[float], p: float) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[int(k)]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


def run_http_burst(
    urls: List[Tuple[str, str]],
    concurrency: int = 10,
    duration_sec: int = 30,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict]:
    """
    urls: spisok (method, url)
    Vozvraschaet metriki po kazhdomu URL.
    """
    stop_at = time.time() + duration_sec
    metrics: Dict[str, Metrics] = {u: Metrics() for _, u in urls}
    lock = threading.Lock()

    def worker(method: str, url: str):
        while time.time() < stop_at:
            code, ms = time_http(method, url, headers=headers)
            with lock:
                metrics[url].add(code, ms)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        for method, url in urls:
            for _ in range(max(1, concurrency // max(1, len(urls)))):
                ex.submit(worker, method, url)

    return {u: m.to_dict() for u, m in metrics.items()}


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--url",
        action="append",
        help="URL dlya nagruzki (mozhno neskolko, metod po umolchaniyu GET)",
        default=[],
    )
    ap.add_argument(
        "--post",
        action="append",
        help="POST URL dlya nagruzki (mozhno neskolko)",
        default=[],
    )
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument(
        "--auth",
        type=str,
        default="",
        help="Znachenie zagolovka Authorization (naprimer, 'Bearer <jwt>')",
    )
    ap.add_argument(
        "--profile-out",
        type=str,
        default="",
        help="Put dlya .prof fayla (optsionalno)",
    )
    args = ap.parse_args()

    urls: List[Tuple[str, str]] = []
    for u in args.url:
        urls.append(("GET", u))
    for u in args.post:
        urls.append(("POST", u))
    headers = {"Authorization": args.auth} if args.auth else None

    if args.profile_out:
        with profile_block(args.profile_out):
            res = run_http_burst(
                urls,
                concurrency=args.concurrency,
                duration_sec=args.duration,
                headers=headers,
            )
    else:
        res = run_http_burst(
            urls,
            concurrency=args.concurrency,
            duration_sec=args.duration,
            headers=headers,
        )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
