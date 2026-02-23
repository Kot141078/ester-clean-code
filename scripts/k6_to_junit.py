# -*- coding: utf-8 -*-
from __future__ import annotations

import glob
import json
import os
import time
import xml.etree.ElementTree as ET
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ART = os.getenv("ART_DIR", "artifacts/perf")
SUITE_NAME = os.getenv("SUITE_NAME", "Ester k6")
P95 = float(os.getenv("P95_LIM_MS", "2000"))
P99 = float(os.getenv("P99_LIM_MS", "5000"))
FAIL_RATE = float(os.getenv("FAIL_RATE", "0.01"))


def load(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def getv(m, metric, key):
    return float(((m.get(metric, {}) or {}).get("values", {}) or {}).get(key, 0.0) or 0.0)


def main():
    os.makedirs(ART, exist_ok=True)
    files = sorted(glob.glob(os.path.join(ART, "*.summary.json")))
    tests = 0
    failures = 0
    tsuite = ET.Element(
        "testsuite",
        {
            "name": SUITE_NAME,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tests": "0",
            "failures": "0",
        },
    )
    for p in files:
        data = load(p)
        metrics = data.get("metrics") or {}
        p95 = getv(metrics, "http_req_duration", "p(95)")
        p99 = getv(metrics, "http_req_duration", "p(99)")
        fr = getv(metrics, "http_req_failed", "rate")
        tcase = ET.SubElement(
            tsuite,
            "testcase",
            {
                "classname": "k6",
                "name": os.path.basename(p),
                "time": str(getv(metrics, "iteration_duration", "avg") / 1000.0 or 0.0),
            },
        )
        tests += 1
        msgs = []
        if p95 > P95:
            msgs.append(f"p95 {p95:.1f}ms > {P95:.1f}ms")
        if p99 > P99:
            msgs.append(f"p99 {p99:.1f}ms > {P99:.1f}ms")
        if fr > FAIL_RATE:
            msgs.append(f"fail_rate {fr:.4f} > {FAIL_RATE:.4f}")
        if msgs:
            failures += 1
            fail = ET.SubElement(
                tcase, "failure", {"message": "; ".join(msgs), "type": "threshold"}
            )
            fail.text = json.dumps(
                {"p95_ms": p95, "p99_ms": p99, "fail_rate": fr}, ensure_ascii=False
            )
    tsuite.set("tests", str(tests))
    tsuite.set("failures", str(failures))
    out = os.path.join(ART, "junit.xml")
    ET.ElementTree(tsuite).write(out, encoding="utf-8", xml_declaration=True)
    print(f"[k6-junit] wrote {out}. tests={tests} failures={failures}")


if __name__ == "__main__":
    main()