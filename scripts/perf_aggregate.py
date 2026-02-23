# -*- coding: utf-8 -*-
import glob
import json
import os
import statistics as st
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ART = os.getenv("ART_DIR", "artifacts/perf")
OUT_JSON = os.path.join(ART, "aggregate.json")
OUT_MD = os.path.join(ART, "report.md")


def getv(metrics, metric, key, default=0.0):
    try:
        return float(
            ((metrics.get(metric, {}) or {}).get("values", {}) or {}).get(key, default) or default
        )
    except Exception:
        return default


def main():
    os.makedirs(ART, exist_ok=True)
    rows = []
    for p in sorted(glob.glob(os.path.join(ART, "*.summary.json"))):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        m = data.get("metrics") or {}
        row = {
            "file": os.path.basename(p),
            "p95_ms": getv(m, "http_req_duration", "p(95)"),
            "p99_ms": getv(m, "http_req_duration", "p(99)"),
            "fail_rate": getv(m, "http_req_failed", "rate"),
            "reqs": getv(m, "http_reqs", "count", 0.0),
            "iterations": getv(m, "iterations", "count", 0.0),
        }
        rows.append(row)

    agg = {}
    if rows:
        agg = {
            "files": len(rows),
            "p95_ms_max": max(r["p95_ms"] for r in rows),
            "p99_ms_max": max(r["p99_ms"] for r in rows),
            "fail_rate_max": max(r["fail_rate"] for r in rows),
            "p95_ms_avg": st.mean(r["p95_ms"] for r in rows),
            "p99_ms_avg": st.mean(r["p99_ms"] for r in rows),
            "fail_rate_avg": st.mean(r["fail_rate"] for r in rows),
            "total_reqs": int(st.fsum(r["reqs"] for r in rows)),
            "total_iterations": int(st.fsum(r["iterations"] for r in rows)),
        }

    out = {"aggregate": agg, "files": rows}
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Markdown report
    lines = ["# Perf aggregate report", ""]
    if agg:
        lines += [
            f"- Files: {agg['files']}",
            f"- Totals: reqs={agg['total_reqs']}, iterations={agg['total_iterations']}",
            f"- Max: p95={agg['p95_ms_max']:.1f} ms, p99={agg['p99_ms_max']:.1f} ms, fail_rate={agg['fail_rate_max']:.4f}",
            f"- Avg: p95={agg['p95_ms_avg']:.1f} ms, p99={agg['p99_ms_avg']:.1f} ms, fail_rate={agg['fail_rate_avg']:.4f}",
            "",
        ]
    lines.append("| file | p95 ms | p99 ms | fail rate | reqs | iterations |")
    lines.append("|------|-------:|-------:|----------:|-----:|-----------:|")
    for r in rows:
        lines.append(
            f"| {r['file']} | {r['p95_ms']:.1f} | {r['p99_ms']:.1f} | {r['fail_rate']:.4f} | {int(r['reqs'])} | {int(r['iterations'])} |"
        )
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[aggregate] wrote {OUT_JSON} and {OUT_MD}")


if __name__ == "__main__":
    main()