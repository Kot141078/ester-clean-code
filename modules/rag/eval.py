# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.rag.eval - offlayn‑otsenka RAG bez vneshnikh embeddingov.

Format primerov (.jsonl):
{"q": "vopros", "gold": ["etalonnyy fragment 1", "fragment 2"]}

Basic metrics:
- hit@k: est li v top‑k retrieval fragment, perekryvayuschiysya po slovam s gold (ili exact sovpadenie id/text).
- coverage: dolya slov voprosa, vstrechayuschikhsya v otvete (0..1).
- jaccard: J(A,B) dlya mnozhestv tokenov gold vs otveta.

ENV:
- ESTER_RAG_EVAL_AB=A|B - A: vklyucheno; B: no-op.

Zemnoy abzats:
Eto kak “shablonnyy indikator na schitke”: daet bystruyu prikidku - ischetsya li nuzhnoe i khvataet li otveta po soderzhaniyu.
# c=a+b"""
import os, json, time, re
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_RAG_EVAL_AB", "A").upper().strip() or "A"
DATA_DIR = os.path.join("data", "rag_eval")
REPORT_JSON = os.path.join(DATA_DIR, "last_report.json")

_word_re = re.compile(r"[A-Za-zA-Yaa-yaEe0-9_]+", re.UNICODE)

def _tok(s: str) -> List[str]:
    return [m.group(0).lower() for m in _word_re.finditer(s or "")]

def _set(s: str) -> set:
    return set(_tok(s))

def _overlap(a: str, b: str) -> float:
    A, B = _set(a), _set(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return inter / float(union)

def _coverage(q: str, ans: str) -> float:
    Q = _set(q)
    if not Q:
        return 0.0
    return len(Q & _set(ans)) / float(len(Q))

def _hub_search(q: str, k:int=3) -> Dict[str, Any]:
    try:
        from modules.rag import hub
        res = hub.search(q, k=k)  # ozhidaetsya {'items':[{'text':..., 'id':..,'score':..}]}
        return dict(res or {})
    except Exception:
        # bezopasnyy fallback
        return {"ok": False, "items": []}

def _rag_answer(q: str, top_k:int=3) -> str:
    # 1) try through a compatible action
    try:
        from modules.thinking import compat_actions as ca
        r = ca.rag_answer(q, top_k=top_k)
        if r and r.get("ok"):
            return str(r.get("text",""))
    except Exception:
        pass
    # 2) fallback na modules.rag.answer
    try:
        from modules.rag import answer as ra
        fn = getattr(ra, "answer", None)
        if callable(fn):
            return str(fn(q, top_k=top_k))
    except Exception:
        pass
    # 3) last fake - empty
    return ""

def _hit_k(q: str, gold: List[str], k:int=3) -> int:
    res = _hub_search(q, k=k)
    items = res.get("items") or []
    for it in items[:k]:
        t = (it.get("text") or "")
        # hit if there is overlap >= 0.2 with any gold
        for g in gold:
            if _overlap(t, g) >= 0.2 or t.strip() == g.strip():
                return 1
    return 0

def evaluate_examples(examples: List[Dict[str, Any]], k:int=3) -> Dict[str, Any]:
    if AB == "B":
        return {"ok": False, "skipped": True, "reason": "AB=B"}
    n = 0
    hit = 0
    cov = 0.0
    jac = 0.0
    rows: List[Dict[str, Any]] = []
    for ex in examples:
        q = str(ex.get("q",""))
        gold = [str(x) for x in (ex.get("gold") or [])]
        if not q or not gold:
            continue
        n += 1
        h = _hit_k(q, gold, k=k)
        hit += h
        ans = _rag_answer(q, top_k=k)
        # we take the best gold for comparison according to Jaccard
        best = max(((_overlap(ans, g), g) for g in gold), default=(0.0, ""))[1]
        cov_i = _coverage(q, ans)
        jac_i = _overlap(ans, best)
        cov += cov_i
        jac += jac_i
        rows.append({"q": q, "ans": ans[:500], "hit": h, "cov": round(cov_i,3), "jac": round(jac_i,3)})
    if n == 0:
        return {"ok": True, "n": 0, "hit@k": 0.0, "cov": 0.0, "jac": 0.0, "rows": []}
    report = {
        "ok": True,
        "n": n,
        "hit@k": hit / float(n),
        "cov": cov / float(n),
        "jac": jac / float(n),
        "k": k,
        "rows": rows[-20:],  # kompaktno
        "ts": int(time.time())
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report

def run_file(path: str, k:int=3) -> Dict[str, Any]:
    examples: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return {"ok": False, "error": "file_not_found", "path": path}
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = (ln or "").strip()
            if not ln: continue
            try:
                examples.append(json.loads(ln))
            except Exception:
                pass
    return evaluate_examples(examples, k=k)