# -*- coding: utf-8 -*-
"""scripts/self_check.py - CLI samoproverki Ester.

MOSTY:
- (Yavnyy) Zapuskaet health-statusy i optsionalno playbook “recover-db”.
- (Skrytyy #1) Vyvodit JSON/tekst; kod vykhoda 0/1 po overall.
- (Skrytyy #2) Bez setevykh zavisimostey; http-proby - tolko esli zadano ENV.

ZEMNOY ABZATs:
Udobno dlya cron/k8s liveness/readiness, a takzhe dlya ruchnoy diagnostiki: “What s Ester pryamo seychas?”

# c=a+b"""
from __future__ import annotations

import argparse
import json
import sys

from modules.selfmanage.health import summary
from modules.selfmanage.playbooks import GARAGE
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--playbook", default=None, help="run garage playbook by name (optional)")
    args = ap.parse_args()

    rep = summary()
    if args.playbook:
        pb = GARAGE.run(args.playbook)
        rep.setdefault("playbook", {"name": pb.name, "ok": pb.ok, "items": pb.items, "took_ms": pb.took_ms})

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"Overall: {rep['overall']}")
        for it in rep["items"]:
            print(f" - {it['name']}: {it['status']} ({it.get('reason','')}) {it['took_ms']}ms")
        if "playbook" in rep:
            p = rep["playbook"]
            print(f"Playbook {p['name']}: {'ok' if p['ok'] else 'fail'} ({p['took_ms']}ms)")
            for x in p["items"]:
                print(f"   * {x['step']}: {x['status']} ({x.get('reason','')})")
    sys.exit(0 if rep["overall"] == "ok" else 1)


if __name__ == "__main__":
    main()