# -*- coding: utf-8 -*-
"""
U2/services/brain/proactive.py — «prokativnoe myshlenie» Ester: smotrim na pamyat i artefakty → reshaem, chto delat.

Mosty:
- Yavnyy: Enderton (logika) — plan kak kompozitsiya proveryaemykh predikatov: ustarelo li A ∧ net li B ∧ izmenilas li tema?.
- Skrytyy #1: Cover & Thomas (infoteoriya) — szhimaem «signaly» sredy (mtime, kheshi tem, schetchiki) do kratkogo plana.
- Skrytyy #2: Ashbi (kibernetika) — regulyator prosche sistemy: A-slot — zhestkie pravila; B-slot — myagkaya perestanovka prioriteta.

Zemnoy abzats (inzheneriya):
ChITAEM TOLKO LOKALNYE FAYLY (ingest-audit, indeks, daydzhesty, obs-metriki, kartochki). Vozvraschaem plan: spisok
deystviy (ingest/index/digest/rules/render/advice/slo/release) i obyasnenie. Zapis sostoyaniya — v `data/cortex/state.json`.
V B-rezhime NE trebuem set: esli LMStudio nedostupen — otkat k A.

# c=a+b
"""
from __future__ import annotations
import glob, json, os, time, hashlib
from typing import Any, Dict, List, Tuple

from services.advisor.topic_extractor import extract_topics  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _p(*parts: str) -> str:
    return os.path.abspath(os.path.join(*parts))

def _persist_dir() -> str:
    return os.getenv("PERSIST_DIR") or _p(os.getcwd(), "data")

def _mtime_or_0(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0

def _latest(globmask: str) -> Tuple[str, float]:
    paths = sorted(glob.glob(globmask))
    if not paths:
        return "", 0.0
    p = paths[-1]
    return p, _mtime_or_0(p)

def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _read_state() -> Dict[str, Any]:
    state_path = _p(_persist_dir(), "cortex", "state.json")
    if os.path.isfile(state_path):
        try:
            return json.load(open(state_path, "r", encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _write_state(st: Dict[str, Any]) -> None:
    base = _p(_persist_dir(), "cortex")
    os.makedirs(base, exist_ok=True)
    with open(_p(base, "state.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)

def _load_policy(policy_path: str | None) -> Dict[str, Any]:
    # Politika s defoltami
    defaults = {
        "ingest_max_age_h": 12,
        "digest_max_age_h": 8,
        "reindex_if_ingested": True,
        "render_always_after_digest": True,
        "apply_rules": True,
        "emit_slo_report": True,
        "slo_every_h": 24,
        "release_enabled": False
    }
    if policy_path and os.path.isfile(policy_path):
        try:
            js = json.load(open(policy_path, "r", encoding="utf-8"))
            defaults.update(js or {})
        except Exception:
            pass
    return defaults

def _topics_fingerprint() -> Tuple[List[str], str]:
    # Berem kontekst iz pamyati (card.tags ∈ {chat,dialog,concern,note,inbox}), formiruem topiki i khesh
    topics = extract_topics(None, top=8) or []
    fp = _sha("|".join(topics)) if topics else ""
    return topics, fp

def think_and_plan(policy_path: str | None = None) -> Dict[str, Any]:
    now = time.time()
    pol = _load_policy(policy_path)
    pd = _persist_dir()

    # Artefakty i vremena
    p_audit = _p(pd, "ingest", "audit.jsonl")
    p_idx_docs = _p(pd, "reco", "tfidf_docs.json")
    p_idx_vocab = _p(pd, "reco", "tfidf_vocab.json")
    dig_dir = _p(pd, "portal", "digests")
    p_digest, t_dig = _latest(os.path.join(dig_dir, "digest_*.json"))
    p_obs = _p(pd, "obs", "metrics.jsonl")

    t_ing = _mtime_or_0(p_audit)
    t_idx = max(_mtime_or_0(p_idx_docs), _mtime_or_0(p_idx_vocab))
    t_obs = _mtime_or_0(p_obs)

    topics, fp = _topics_fingerprint()
    st = _read_state()
    prev_fp = st.get("topics_fp","")
    topics_changed = bool(fp and fp != prev_fp)

    actions: List[str] = []
    explain: List[str] = []

    # 1) Nuzhen li ingest?
    if (now - t_ing) / 3600.0 > float(pol["ingest_max_age_h"]):
        actions.append("ingest")
        explain.append("ingest: audit starshe poroga")

    # 2) Nuzhen li reindex?
    if pol.get("reindex_if_ingested", True) and (t_ing > t_idx):
        actions.append("index")
        explain.append("index: indeks staree poslednikh ingenstov")

    # 3) digest, esli net/staryy/temy izmenilis
    need_digest = (t_dig == 0.0) or ((now - t_dig)/3600.0 > float(pol["digest_max_age_h"])) or topics_changed
    if need_digest:
        actions.append("digest")
        explain.append("digest: net/ustarel/temy izmenilis")

    # 4) rules
    if pol.get("apply_rules", True):
        actions.append("rules")

    # 5) render
    if pol.get("render_always_after_digest", True) or need_digest:
        actions.append("render")

    # 6) advice (sovet)
    actions.append("advice")

    # 7) SLO
    if pol.get("emit_slo_report", True):
        if (now - t_obs)/3600.0 > float(pol.get("slo_every_h", 24)):
            actions.append("slo")

    # 8) release (optsionalno)
    if pol.get("release_enabled", False):
        actions.append("release")

    # A/B — tolko perestanovka prioritetov (bez izmeneniya nabora deystviy)
    mode = (os.getenv("U2_MODE") or "A").strip().upper()
    if mode == "B":
        try:
            # myagko: esli LMStudio dostupen — dadim emu predlozhit uporyadochivanie
            from services.reco.llm_client import LMStudioClient  # type: ignore
            client = LMStudioClient()
            msg = [
                {"role":"system","content":"Uporyadochit shagi payplayna po ubyvaniyu polzy: ingest, index, digest, rules, render, advice, slo, release. Verni JSON {order:[...]}. Bez poyasneniy."},
                {"role":"user","content":json.dumps({"actions":actions, "signals":{"topics_changed":topics_changed}}, ensure_ascii=False)}
            ]
            js = json.loads(client.chat(msg, max_tokens=100, temperature=0.0))
            order = [a for a in js.get("order", []) if a in actions]
            if order:
                actions = order + [a for a in actions if a not in order]
        except Exception:
            pass  # avtokatbek v A

    plan = {"actions": actions, "explain": explain, "topics": topics, "topics_fp": fp}
    return plan

def commit_state(topics_fp: str) -> None:
    st = _read_state()
    st["topics_fp"] = topics_fp
    st["ts"] = int(time.time())
    _write_state(st)