# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
JWT = os.getenv("ESTER_JWT", "")
CONFIG_PATH = os.getenv("PROBE_CONFIG", "scripts/perf_endpoints.json")
ART_DIR = "artifacts/perf"
os.makedirs(ART_DIR, exist_ok=True)

HEADERS_GET, HEADERS_JSON = {}, {"Content-Type": "application/json"}
if JWT:
    HEADERS_GET["Authorization"] = f"Bearer {JWT}"
    HEADERS_JSON["Authorization"] = f"Bearer {JWT}"


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if os.getenv("PROBE_ITER"):
        cfg["iterations"] = int(os.getenv("PROBE_ITER"))
    if os.getenv("PROBE_CONC"):
        cfg["concurrency"] = int(os.getenv("PROBE_CONC"))
    if os.getenv("PROBE_SLEEP_MS"):
        cfg["sleep_ms"] = int(os.getenv("PROBE_SLEEP_MS"))
    return cfg


def pct(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


@dataclass
class Result:
    name: str
    count: int = 0
    failures: int = 0
    durations_ms: List[float] = None

    def __post_init__(self):
        self.durations_ms = self.durations_ms or []

    def record(self, ok: bool, dur_ms: float):
        self.count += 1
        self.failures += 0 if ok else 1
        self.durations_ms.append(dur_ms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "failures": self.failures,
            "fail_rate": (self.failures / self.count) if self.count else 0.0,
            "p95_ms": pct(self.durations_ms, 95),
            "p99_ms": pct(self.durations_ms, 99),
        }


def worker(
    wid: int,
    jobs: "queue.Queue[Tuple[Dict[str,Any], int]]",
    res_map: Dict[str, Result],
    allowed: set,
    sleep_ms: int,
):
    import time as _t

    sess = requests.Session()
    while True:
        try:
            ep, _ = jobs.get_nowait()
        except queue.Empty:
            break
        method = (ep.get("method") or "GET").upper()
        path = ep.get("path") or "/"
        url = BASE + path
        headers = HEADERS_GET if method == "GET" else HEADERS_JSON
        body = ep.get("body")
        t0 = _t.perf_counter()
        ok = False
        try:
            if method == "GET":
                r = sess.get(url, headers=headers, timeout=15)
            elif method == "POST":
                data = body if isinstance(body, (dict, list)) else (body or {})
                r = sess.post(url, headers=headers, json=data, timeout=30)
            else:
                r = sess.request(method, url, headers=headers, json=body, timeout=30)
            ok = r.status_code in allowed
        except Exception:
            ok = False
        dur_ms = (_t.perf_counter() - t0) * 1000.0
        key = f"{method} {path}"
        res = res_map.setdefault(key, Result(name=key))
        res.record(ok, dur_ms)
        if sleep_ms > 0:
            _t.sleep(sleep_ms / 1000.0)


def run_probe(cfg: Dict[str, Any]) -> Dict[str, Any]:
    iterations = int(cfg.get("iterations", 200))
    concurrency = int(cfg.get("concurrency", 5))
    sleep_ms = int(cfg.get("sleep_ms", 50))
    allowed = set(
        int(x) for x in cfg.get("allowed_statuses", [200, 201, 202, 204, 400, 401, 403, 404])
    )
    endpoints = cfg.get("endpoints", [])

    jobs: "queue.Queue[Tuple[Dict[str,Any],int]]" = queue.Queue()
    for i in range(iterations):
        ep = (
            endpoints[i % max(1, len(endpoints))]
            if endpoints
            else {"method": "GET", "path": "/health"}
        )
        jobs.put((ep, i))

    res_map: Dict[str, Result] = {}
    threads: List[threading.Thread] = []
    for w in range(concurrency):
        t = threading.Thread(target=worker, args=(w, jobs, res_map, allowed, sleep_ms), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    results = [res.to_dict() for _, res in sorted(res_map.items(), key=lambda kv: kv[0])]
    total = sum(r["count"] for r in results)
    fails = sum(r["failures"] for r in results)
    agg = {
        "total_count": total,
        "total_failures": fails,
        "fail_rate_max": max((r["fail_rate"] for r in results), default=0.0),
        "p95_ms_max": max((r["p95_ms"] for r in results), default=0.0),
        "p99_ms_max": max((r["p99_ms"] for r in results), default=0.0),
    }

    return {
        "results": results,
        "aggregate": agg,
        "config": cfg,
        "base_url": BASE,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def write_reports(data: Dict[str, Any]):
    jpath = os.path.join(ART_DIR, "latency_probe.json")
    mpath = os.path.join(ART_DIR, "report_latency.md")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    lines = [
        "# Latency probe report",
        f"- Base: {data.get('base_url')}",
        f"- Generated: {data.get('generated_at')}",
    ]
    agg = data["aggregate"]
    lines += [
        f"- Totals: count={agg['total_count']}, failures={agg['total_failures']}",
        f"- Max: p95={agg['p95_ms_max']:.1f} ms, p99={agg['p99_ms_max']:.1f} ms, fail_rate={agg['fail_rate_max']:.4f}",
        "",
        "| endpoint | count | failures | fail_rate | p95 ms | p99 ms |",
        "|----------|------:|---------:|----------:|-------:|-------:|",
    ]
    for r in data["results"]:
        lines.append(
            f"| {r['name']} | {r['count']} | {r['failures']} | {r['fail_rate']:.4f} | {r['p95_ms']:.1f} | {r['p99_ms']:.1f} |"
        )
    with open(mpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[probe] wrote {jpath} and {mpath}")


def main():
    cfg = load_config(CONFIG_PATH)
    data = run_probe(cfg)
    write_reports(data)


if __name__ == "__main__":
    main()