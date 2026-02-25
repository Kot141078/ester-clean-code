#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R7/tools/r7_slo_report.py - otchet po SLO na osnove jsonl-metrik.

Mosty:
- Yavnyy: Enderton - SLO kak formalnye predikaty (uspeshnost/latentnost) nad oknom nablyudeniy.
- Skrytyy #1: Cover & Thomas — agregiruem “signal” (rc/ms), prevraschaya potok nablyudeniy v kratkiy Markdown.
- Skrytyy #2: Ashbi — A/B-slot cherez R7_MODE dlya dop. statistiki, pri oshibkakh — katbek.

Zemnoy abzats (inzheneriya):
Chitaet `PERSIST_DIR/obs/metrics.jsonl`, filtruet po oknu `R7_SLO_WINDOW_DAYS`, primenyaet pravila iz config JSON:
  {
    "targets": [
      {"name":"cmd:r3_index", "match":{"cmd_has":"tools/r3_index_build.py"}, "slo":{"success_rate":0.95,"p95_ms":5000}}
    ]
  }
Write Markdown-otchet s Pass/Fail. No matter what.

# c=a+b"""
from __future__ import annotations
import argparse, json, os, time, statistics
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _metrics_path():
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    return os.path.join(base, "obs", "metrics.jsonl")

def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    return out

def _percentile(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = max(0, min(len(xs)-1, int(round((p/100.0)*(len(xs)-1)))))
    return float(xs[k])

def _match(rec: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    # Supports only simple conditions: smd_us, tag_ek, name_ek
    m = rule or {}
    if "cmd_has" in m:
        cmd = " ".join([str(x) for x in (rec.get("cmd") or [])])
        if m["cmd_has"] not in cmd:
            return False
    if "tag_eq" in m:
        if str(rec.get("tag","")) != str(m["tag_eq"]):
            return False
    if "name_eq" in m:
        if str(rec.get("name","")) != str(m["name_eq"]):
            return False
    return True

def _within_window(ts: float, days: int) -> bool:
    if days <= 0:
        return True
    return (time.time() - float(ts)) <= days*86400.0

def main() -> int:
    ap = argparse.ArgumentParser(description="SLO report over metrics.jsonl")
    ap.add_argument("--config", required=True, help="JSON-fayl s tselyami SLO")
    ap.add_argument("--out", default="-", help="Path Markdovn report or b-b")
    args = ap.parse_args()

    cfg = json.load(open(args.config, "r", encoding="utf-8"))
    window_days = int(os.getenv("R7_SLO_WINDOW_DAYS") or cfg.get("window_days") or 14)

    recs = [r for r in _read_jsonl(_metrics_path()) if _within_window(r.get("ts", 0), window_days)]

    lines = []
    lines.append(f"# SLO Report (last {window_days} days)\n")

    for tgt in (cfg.get("targets") or []):
        name = tgt.get("name","unnamed")
        match = tgt.get("match") or {}
        slo = tgt.get("slo") or {}
        want_sr = float(slo.get("success_rate", 0.0))
        want_p95 = float(slo.get("p95_ms", 0.0))

        # sobiraem cmd-zapisi
        xs = [r for r in recs if r.get("type")=="record" and r.get("name")=="cmd" and _match(r, match)]
        n = len(xs)
        oks = [r for r in xs if int(r.get("rc",1)) == 0]
        sr = (len(oks) / n) if n else 0.0
        p95 = _percentile([float(r.get("ms",0.0)) for r in xs], 95) if n else 0.0

        pass_sr = (sr >= want_sr) if want_sr>0 else True
        pass_p = (p95 <= want_p95) if want_p95>0 else True
        status = "PASS" if (pass_sr and pass_p) else "FAIL"

        lines.append(f"## {name} — **{status}**")
        lines.append(f"- Samples: {n}, Success: {len(oks)} ({sr:.1%})")
        if want_sr>0: lines.append(f"- Target success_rate ≥ {want_sr:.0%}")
        if want_p95>0: lines.append(f"- p95 latency: {int(p95)} ms (target ≤ {int(want_p95)} ms)")
        if xs:
            lines.append(f"- Last cmd: `{' '.join(str(x) for x in (xs[-1].get('cmd') or []))}`")
        lines.append("")

    md = "\n".join(lines)
    if args.out == "-":
        print(md)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"[r7_slo_report] written: {args.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# c=a+b