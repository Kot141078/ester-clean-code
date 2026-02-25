# -*- coding: utf-8 -*-
"""tests/stress_search.py ​​- nagruzochnyy test poiska (RAG L1→L2) s latentnostyami p50/p90/p99.

Name:
  • Generiruet potok zaprosov k /rag/query (POST), izmeryaet vremya total/coarse/fine.
  • Prostaya mnogopotochnost bez vneshnikh zavisimostey (threading + urllib).
  • Pechataet raspredeleniya i srednie znacheniya; help podtverdit SLA ≤200 ms.

CLI:
  python tests/stress_search.py --qps 30 --sec 20 --url http://127.0.0.1:8080/rag/query --chap 5 --chunks 5

Zemnoy abzats (inzheneriya):
Eto "dinamometr" poiska: podaem nagruzku i izmeryaem otdachu. Vidno, khvataet li “reduktora” coarse→fine
i ne buksuet li IVF/cash.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): kontroliruemoe vozbuzhdenie sistemy — otsenka ustoychivosti kontura poiska.
- Skrytyy 1 (Infoteoriya ↔ Ekonomika): deshevye zaprosy (cash) dolzhny gasit stoimost chastogo znaniya.
- Skrytyy 2 (Anatomiya ↔ PO): kak spiroergometriya - izmeryaem “dykhanie” (latency) pod nagruzkoy.

# c=a+b"""
from __future__ import annotations

import argparse, json, random, string, threading, time, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _rand_query():
    vocab = ["informatsiya","algoritm","gipoteza","sistema","energiya","glava","teoriya","bayes","entropiya","shennon","korpus","oshibka","regulyator","pamyat","glava 1","glava 2"]
    k = random.randint(2,4)
    return " ".join(random.sample(vocab, k))

def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8","ignore")
    t1 = time.time()
    j = json.loads(body)
    j["_elapsed_ms"] = 1000.0 * (t1 - t0)
    return j

def _percentile(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    i = int(round((len(s)-1)*p))
    return s[max(0, min(len(s)-1, i))]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080/rag/query")
    ap.add_argument("--qps", type=int, default=20)
    ap.add_argument("--sec", type=int, default=15)
    ap.add_argument("--chap", type=int, default=5)
    ap.add_argument("--chunks", type=int, default=5)
    args = ap.parse_args()

    stop_at = time.time() + args.sec
    mtx = threading.Lock()
    totals, coarse, fine = [], [], []
    hits = 0
    errs = 0

    def worker():
        nonlocal hits, errs
        while time.time() < stop_at:
            q = _rand_query()
            try:
                j = _post(args.url, {"q": q, "topk_chapters": args.chap, "topk_chunks": args.chunks})
                with mtx:
                    totals.append(j.get("timings_ms",{}).get("total") or j.get("_elapsed_ms",0.0))
                    coarse.append(j.get("timings_ms",{}).get("coarse", 0.0))
                    fine.append(j.get("timings_ms",{}).get("fine", 0.0))
                    hits += 1
            except Exception:
                with mtx:
                    errs += 1
            time.sleep(1.0 / max(1, args.qps))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, args.qps//5))]
    for t in threads: t.start()
    for t in threads: t.join()

    out = {
        "requests_ok": hits,
        "requests_err": errs,
        "p50_ms": round(_percentile(totals, 0.50),2),
        "p90_ms": round(_percentile(totals, 0.90),2),
        "p99_ms": round(_percentile(totals, 0.99),2),
        "avg_ms": round(sum(totals)/max(1,len(totals)),2),
        "avg_coarse_ms": round(sum(coarse)/max(1,len(coarse)),2),
        "avg_fine_ms": round(sum(fine)/max(1,len(fine)),2),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()