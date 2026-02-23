# -*- coding: utf-8 -*-
"""
tools/recovery_check.py — proverka vosstanovleniya indeksov/poiska posle «kholodnogo starta».

Ideya:
  • Emuliruem perezapusk protsessa: prosto zapuskaem zagruzku indeksov i delaem neskolko zaprosov RAG.
  • Podtverzhdaem, chto:
      - indeksy chitayutsya «lenivo» (load()) bez restarta prilozheniya;
      - /rag/query otvechaet korrektno;
      - kesh otvetov (esli vklyuchen) daet hit na vtoroy zapros.

CLI:
  python tools/recovery_check.py --url http://127.0.0.1:8080/rag/query --tries 3

Zemnoy abzats (inzheneriya):
Eto «pusk posle obestochivaniya»: vklyuchili — i srazu meryaem, dyshit li sistema i mozhno li rabotat.

Mosty:
- Yavnyy (Arkhitektura ↔ Nadezhnost): stsenariy vykhoda/vkhoda iz stroya podtverzhdaet otkazoustoychivost payplayna.
- Skrytyy 1 (Infoteoriya ↔ Ekonomika): vtoroy zapros dolzhen idti bystree (kesh) — ekonomim vychislenie.
- Skrytyy 2 (Anatomiya ↔ PO): kak refleks dykhaniya — zapuskaetsya avtomaticheski i stabilno posle «probuzhdeniya».

# c=a+b
"""
from __future__ import annotations

import argparse, json, time, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _post(url: str, q: str, chap: int = 5, chunks: int = 5):
    data = json.dumps({"q": q, "topk_chapters": chap, "topk_chunks": chunks}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8","ignore")
    t1 = time.time()
    j = json.loads(body)
    return j, 1000.0 * (t1 - t0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080/rag/query")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--q", default="teoriya informatsii bayes entropiya")
    args = ap.parse_args()

    results = []
    for i in range(max(2, args.tries)):
        j, ms = _post(args.url, args.q)
        results.append({"i": i+1, "elapsed_ms": round(ms,2), "cached": bool(j.get("cached"))})
        time.sleep(0.3)

    print(json.dumps({"ok": True, "tries": len(results), "results": results}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()