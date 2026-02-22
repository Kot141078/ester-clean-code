# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.curiosity import curiosity_planner, unknown_detector
from modules.garage import agent_factory, agent_queue
from modules.memory.facade import memory_add

_SLOTB_ERR_STREAK = 0
_SLOTB_DISABLED = False
_SLOTB_LAST_FALLBACK_REASON = ""
_SLOTB_LAST_FALLBACK_TS = 0


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _safe_int(value: Any, default: int, *, min_value: int = 0) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    return max(min_value, out)


def _safe_float(value: Any, default: float, *, min_value: float = 0.0, max_value: float = 1.0) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    if out < min_value:
        out = min_value
    if out > max_value:
        out = max_value
    return out


def _slot_raw() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _slot_effective() -> str:
    if _SLOTB_DISABLED:
        return "A"
    return _slot_raw()


def _slot_b_fail_max() -> int:
    return _safe_int(os.getenv("ESTER_CURIOSITY_SLOTB_FAIL_MAX", "3"), 3, min_value=1)


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _curiosity_root() -> Path:
    p = (_persist_dir() / "curiosity").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _evidence_root() -> Path:
    p = (_curiosity_root() / "evidence").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ticket_dir(ticket_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_\-]+", "_", str(ticket_id or "").strip()) or "ticket"
    p = (_evidence_root() / safe).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now_ts() -> int:
    return int(time.time())


def _sha256_hex(blob: bytes) -> str:
    import hashlib

    return hashlib.sha256(blob).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_hex(str(text or "").encode("utf-8"))


def _json_canonical_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(dict(payload or {}), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_evidence(ticket_id: str, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    ts = _now_ts()
    safe_kind = re.sub(r"[^a-zA-Z0-9_\-]+", "_", str(kind or "").strip()) or "event"
    p = (_ticket_dir(ticket_id) / f"{ts}_{safe_kind}.json").resolve()
    blob = json.dumps(dict(payload or {}), ensure_ascii=False, indent=2).encode("utf-8")
    p.write_bytes(blob)
    sha = _sha256_hex(blob)
    return {
        "path": str(p),
        "rel_path": str(p.relative_to(_persist_dir())).replace("\\", "/"),
        "sha256": sha,
        "kind": safe_kind,
        "ts": ts,
    }


def _find_latest_evidence(ticket_id: str, prefixes: List[str]) -> Dict[str, Any]:
    folder = _ticket_dir(ticket_id)
    rows: List[Path] = []
    for p in folder.glob("*.json"):
        name = p.name.lower()
        if any(name.endswith(f"_{pref}.json".lower()) for pref in prefixes):
            rows.append(p)
    rows.sort(key=lambda x: x.name)
    if not rows:
        return {}
    chosen = rows[-1]
    try:
        payload = json.loads(chosen.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    raw = chosen.read_bytes()
    return {
        "path": str(chosen),
        "rel_path": str(chosen.relative_to(_persist_dir())).replace("\\", "/"),
        "sha256": _sha256_hex(raw),
        "payload": dict(payload) if isinstance(payload, dict) else {},
    }


def _tokenize(text: str) -> List[str]:
    return [x for x in re.findall(r"[A-Za-zA-Yaa-ya0-9_]{3,}", str(text or "").lower()) if x]


def _load_local_corpus(limit: int = 2400) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = 0
    candidates = [
        (_persist_dir() / "memory" / "fallback_notes.jsonl").resolve(),
        (_persist_dir() / "passport" / "clean_memory.jsonl").resolve(),
    ]
    for path in candidates:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if seen >= limit:
                    return out
                s = line.strip()
                if not s:
                    continue
                try:
                    row = json.loads(s)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                text = ""
                if "text" in row:
                    text = str(row.get("text") or "")
                elif path.name == "clean_memory.jsonl":
                    vals = []
                    for key in ("role_user", "role_assistant", "role_system", "role_misc"):
                        val = str(row.get(key) or "").strip()
                        if val:
                            vals.append(val)
                    text = " ".join(vals).strip()
                if not text:
                    continue
                out.append({"source": str(path.name), "text": text[:4000]})
                seen += 1
    return out


def _rank_hits(query: str, rows: List[Dict[str, Any]], max_docs: int) -> List[Dict[str, Any]]:
    tokens = _tokenize(query)
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for row in rows:
        text = str(row.get("text") or "")
        if not text:
            continue
        low = text.lower()
        score = 0
        for tok in tokens:
            if tok in low:
                score += 1
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "source": str(row.get("source") or ""),
                    "score": score,
                    "text": text[:500],
                },
            )
        )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[: max(1, int(max_docs))]]


def _ticket_meta(ticket_id: str, fallback_query: str = "") -> Dict[str, Any]:
    folded = unknown_detector.fold_tickets()
    row = dict((folded.get("tickets_by_id") or {}).get(str(ticket_id or ""), {}) or {})
    return {
        "ticket_id": str(ticket_id or ""),
        "query": str(row.get("query") or fallback_query or ""),
        "source": str(row.get("source") or "dialog"),
        "priority": _safe_float(row.get("priority"), 0.5),
        "budgets": dict(row.get("budgets") or {}),
        "status": str(row.get("status") or "open"),
    }


def _l4w_build_for_ticket(
    *,
    ticket_id: str,
    summary: str,
    evidence_rel_path: str,
    evidence_sha256: str,
    decision_kind: str,
) -> Dict[str, Any]:
    try:
        from modules.runtime import l4w_witness
    except Exception:
        l4w_witness = None  # type: ignore
    if l4w_witness is None:
        return {"ok": False, "error": "l4w_unavailable"}

    agent_id = "curiosity"
    head = l4w_witness.chain_head(agent_id)
    prev_hash = str(head.get("envelope_hash") or "") if bool(head.get("has_head")) else ""
    build = l4w_witness.build_envelope_for_clear(
        agent_id=agent_id,
        quarantine_event_id=str(ticket_id),
        reviewer="curiosity_researcher",
        summary=f"{decision_kind}: {summary}",
        notes=f"ticket:{ticket_id}",
        evidence_path=str(evidence_rel_path),
        evidence_sha256=str(evidence_sha256).lower(),
        evidence_schema="ester.curiosity.evidence.v1",
        evidence_sig_ok=False,
        evidence_payload_hash=str(evidence_sha256).lower(),
        prev_hash=prev_hash,
        on_time=True,
        late=False,
        ts=_now_ts(),
    )
    if not bool(build.get("ok")):
        return {"ok": False, "error": str(build.get("error") or "l4w_build_failed"), "error_code": str(build.get("error_code") or "")}

    sign = l4w_witness.sign_envelope(dict(build.get("envelope") or {}), key_id="curiosity")
    if not bool(sign.get("ok")):
        return {"ok": False, "error": str(sign.get("error") or "l4w_sign_failed"), "error_code": str(sign.get("error_code") or "")}

    write = l4w_witness.write_envelope(agent_id, dict(sign.get("envelope") or {}))
    if not bool(write.get("ok")):
        return {"ok": False, "error": str(write.get("error") or "l4w_write_failed"), "error_code": str(write.get("error_code") or "")}

    append = l4w_witness.append_chain_record(
        agent_id,
        quarantine_event_id=str(ticket_id),
        envelope_id=str((sign.get("envelope") or {}).get("envelope_id") or ""),
        envelope_hash=str(sign.get("envelope_hash") or ""),
        prev_hash=str(build.get("prev_hash") or ""),
        envelope_path=str(write.get("envelope_rel_path") or ""),
        envelope_sha256=str(write.get("envelope_sha256") or ""),
        ts=_now_ts(),
    )
    if not bool(append.get("ok")):
        return {"ok": False, "error": str(append.get("error") or "l4w_chain_failed"), "error_code": str(append.get("error_code") or "")}

    return {
        "ok": True,
        "envelope_hash": str(sign.get("envelope_hash") or ""),
        "envelope_path": str(write.get("envelope_rel_path") or ""),
        "envelope_sha256": str(write.get("envelope_sha256") or ""),
        "prev_hash": str(build.get("prev_hash") or ""),
        "pub_fingerprint": str(sign.get("pub_fingerprint") or ""),
    }


def action_local_search(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    ticket_id = str(payload.get("ticket_id") or "").strip()
    query = str(payload.get("query") or "").strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id_required"}
    if not query:
        return {"ok": False, "error": "query_required"}
    max_docs = _safe_int(payload.get("max_docs"), 12, min_value=1)
    corpus = _load_local_corpus(limit=_safe_int(payload.get("corpus_limit"), 2400, min_value=50))
    hits = _rank_hits(query, corpus, max_docs=max_docs)
    evidence = _write_evidence(
        ticket_id,
        "local_search",
        {
            "schema": "ester.curiosity.evidence.v1",
            "kind": "local_search",
            "ticket_id": ticket_id,
            "query": query,
            "hits": hits,
            "hits_total": len(hits),
            "ts": _now_ts(),
        },
    )
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "query": query,
        "hits_total": len(hits),
        "hits": hits,
        "evidence": {"path": evidence["rel_path"], "sha256": evidence["sha256"]},
    }


def action_local_extract(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    ticket_id = str(payload.get("ticket_id") or "").strip()
    query = str(payload.get("query") or "").strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id_required"}
    evidence_src = _find_latest_evidence(ticket_id, ["local_search"])
    hits = list((evidence_src.get("payload") or {}).get("hits") or [])
    top_k = _safe_int(payload.get("top_k"), 8, min_value=1)
    candidates: List[Dict[str, Any]] = []
    seen = set()
    for hit in hits:
        text = str((hit or {}).get("text") or "").strip()
        if not text:
            continue
        chunks = re.split(r"[.!?]\s+", text)
        for chunk in chunks:
            c = chunk.strip()
            if len(c) < 20:
                continue
            key = c.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"text": c[:280], "source": str((hit or {}).get("source") or "")})
            if len(candidates) >= top_k:
                break
        if len(candidates) >= top_k:
            break
    evidence = _write_evidence(
        ticket_id,
        "local_extract",
        {
            "schema": "ester.curiosity.evidence.v1",
            "kind": "local_extract",
            "ticket_id": ticket_id,
            "query": query,
            "candidates": candidates,
            "from": {"path": evidence_src.get("rel_path", ""), "sha256": evidence_src.get("sha256", "")},
            "ts": _now_ts(),
        },
    )
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "candidates_total": len(candidates),
        "candidates": candidates,
        "evidence": {"path": evidence["rel_path"], "sha256": evidence["sha256"]},
    }


def action_local_crosscheck(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    ticket_id = str(payload.get("ticket_id") or "").strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id_required"}
    min_sources = _safe_int(payload.get("min_sources"), 2, min_value=1)
    ext = _find_latest_evidence(ticket_id, ["local_extract"])
    search = _find_latest_evidence(ticket_id, ["local_search"])
    candidates = list((ext.get("payload") or {}).get("candidates") or [])
    search_hits = list((search.get("payload") or {}).get("hits") or [])
    sources = sorted({str((x or {}).get("source") or "") for x in search_hits if str((x or {}).get("source") or "")})
    crosscheck_ok = bool(candidates) and len(sources) >= min_sources
    evidence = _write_evidence(
        ticket_id,
        "local_crosscheck",
        {
            "schema": "ester.curiosity.evidence.v1",
            "kind": "local_crosscheck",
            "ticket_id": ticket_id,
            "crosscheck_ok": crosscheck_ok,
            "sources_total": len(sources),
            "sources": sources,
            "candidates_total": len(candidates),
            "from_extract": {"path": ext.get("rel_path", ""), "sha256": ext.get("sha256", "")},
            "from_search": {"path": search.get("rel_path", ""), "sha256": search.get("sha256", "")},
            "ts": _now_ts(),
        },
    )
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "crosscheck_ok": crosscheck_ok,
        "sources_total": len(sources),
        "sources": sources,
        "evidence": {"path": evidence["rel_path"], "sha256": evidence["sha256"]},
    }


def _append_ticket_result(
    *,
    ticket_id: str,
    event: str,
    kind: str,
    summary: str,
    evidence_sha: str,
    l4w_hash: str,
    source: str,
    query: str,
    priority: float,
    budgets: Dict[str, Any],
    error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rep = unknown_detector.append_ticket_event(
        event=event,
        ticket_id=ticket_id,
        source=source,
        query=query,
        context_text=summary,
        priority=priority,
        budgets=budgets,
        status=("resolved" if event in {"resolve", "negative"} else "failed" if event == "fail" else ""),
        result={
            "kind": kind,
            "summary": summary,
            "evidence_ref": {"sha256": str(evidence_sha or ""), "l4w_envelope_hash": str(l4w_hash or "")},
        },
        error=error,
    )
    return rep


def action_crystallize_negative(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    ticket_id = str(payload.get("ticket_id") or "").strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id_required"}
    meta = _ticket_meta(ticket_id, fallback_query=str(payload.get("query") or ""))
    ev = _find_latest_evidence(ticket_id, ["local_crosscheck", "local_extract", "local_search", "web_search"])
    evidence_sha = str(ev.get("sha256") or "")
    evidence_rel = str(ev.get("rel_path") or "")
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        summary = f"No reliable evidence found for: {meta['query']}"
    l4w = _l4w_build_for_ticket(
        ticket_id=ticket_id,
        summary=summary,
        evidence_rel_path=evidence_rel,
        evidence_sha256=evidence_sha,
        decision_kind="negative",
    )
    l4w_hash = str(l4w.get("envelope_hash") or "")
    rec = memory_add(
        "fact",
        summary,
        meta={
            "ticket_id": ticket_id,
            "curiosity_result": "negative",
            "evidence_sha256": evidence_sha,
            "l4w_envelope_hash": l4w_hash,
            "source": "curiosity.crystallize.negative",
        },
    )
    rep = _append_ticket_result(
        ticket_id=ticket_id,
        event="negative",
        kind="negative",
        summary=summary,
        evidence_sha=evidence_sha,
        l4w_hash=l4w_hash,
        source=str(meta.get("source") or "dialog"),
        query=str(meta.get("query") or ""),
        priority=_safe_float(meta.get("priority"), 0.5),
        budgets=dict(meta.get("budgets") or {}),
    )
    return {
        "ok": bool(rep.get("ok")),
        "ticket_id": ticket_id,
        "kind": "negative",
        "summary": summary,
        "memory_id": str((rec or {}).get("id") or ""),
        "evidence_ref": {"sha256": evidence_sha, "path": evidence_rel},
        "l4w": l4w,
    }


def action_crystallize_fact(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    ticket_id = str(payload.get("ticket_id") or "").strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id_required"}

    meta = _ticket_meta(ticket_id, fallback_query=str(payload.get("query") or ""))
    cross = _find_latest_evidence(ticket_id, ["local_crosscheck"])
    ext = _find_latest_evidence(ticket_id, ["local_extract"])
    cross_ok = bool((cross.get("payload") or {}).get("crosscheck_ok"))
    candidates = list((ext.get("payload") or {}).get("candidates") or [])

    if (not cross_ok) or (not candidates):
        return action_crystallize_negative(
            {
                "ticket_id": ticket_id,
                "query": meta.get("query"),
                "summary": f"Crosscheck failed or evidence insufficient for: {meta.get('query')}",
            }
        )

    top = dict(candidates[0] or {})
    summary = str(top.get("text") or "").strip()
    if not summary:
        return action_crystallize_negative({"ticket_id": ticket_id, "query": meta.get("query")})

    evidence_sha = str(cross.get("sha256") or ext.get("sha256") or "")
    evidence_rel = str(cross.get("rel_path") or ext.get("rel_path") or "")
    l4w = _l4w_build_for_ticket(
        ticket_id=ticket_id,
        summary=summary,
        evidence_rel_path=evidence_rel,
        evidence_sha256=evidence_sha,
        decision_kind="fact",
    )
    l4w_hash = str(l4w.get("envelope_hash") or "")
    rec = memory_add(
        "fact",
        summary,
        meta={
            "ticket_id": ticket_id,
            "curiosity_result": "fact",
            "evidence_sha256": evidence_sha,
            "l4w_envelope_hash": l4w_hash,
            "source": "curiosity.crystallize.fact",
        },
    )
    rep = _append_ticket_result(
        ticket_id=ticket_id,
        event="resolve",
        kind="fact",
        summary=summary,
        evidence_sha=evidence_sha,
        l4w_hash=l4w_hash,
        source=str(meta.get("source") or "dialog"),
        query=str(meta.get("query") or ""),
        priority=_safe_float(meta.get("priority"), 0.5),
        budgets=dict(meta.get("budgets") or {}),
    )
    return {
        "ok": bool(rep.get("ok")),
        "ticket_id": ticket_id,
        "kind": "fact",
        "summary": summary,
        "memory_id": str((rec or {}).get("id") or ""),
        "evidence_ref": {"sha256": evidence_sha, "path": evidence_rel},
        "l4w": l4w,
    }


def action_close_ticket(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    ticket_id = str(payload.get("ticket_id") or "").strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id_required"}
    meta = _ticket_meta(ticket_id, fallback_query=str(payload.get("query") or ""))
    status = str(meta.get("status") or "")
    if status in {"resolved", "failed"}:
        return {"ok": True, "ticket_id": ticket_id, "status": status, "noop": True}

    event = str(payload.get("default_event") or "resolve").strip().lower()
    if event not in {"resolve", "negative", "fail", "stale"}:
        event = "resolve"
    err = None
    if event == "fail":
        err = {"code": "manual_close_fail", "detail": "closed_by_close.ticket"}
    rep = unknown_detector.append_ticket_event(
        event=event,
        ticket_id=ticket_id,
        source=str(meta.get("source") or "dialog"),
        query=str(meta.get("query") or ""),
        context_text="close.ticket",
        priority=_safe_float(meta.get("priority"), 0.5),
        budgets=dict(meta.get("budgets") or {}),
        status=("failed" if event == "fail" else "stale" if event == "stale" else "resolved"),
        error=err,
    )
    return {"ok": bool(rep.get("ok")), "ticket_id": ticket_id, "event": event}


def action_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(args or {})
    ticket_id = str(payload.get("ticket_id") or "").strip()
    query = str(payload.get("query") or "").strip()
    if not ticket_id:
        return {"ok": False, "error": "ticket_id_required"}
    if not query:
        return {"ok": False, "error": "query_required"}

    from modules.runtime import execution_window

    win = execution_window.current_window()
    if not bool(win.get("open")):
        return {"ok": False, "error": "window_closed", "policy_hit": "curiosity.web.window"}

    allow_web = _truthy(os.getenv("ESTER_CURIOSITY_WEB_ENABLE", "0")) and _truthy(
        os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")
    )
    if not allow_web:
        return {"ok": False, "error": "web_policy_denied", "policy_hit": "curiosity.web.policy"}

    allowed_domains = {
        str(x).strip().lower()
        for x in str(os.getenv("ESTER_CURIOSITY_WEB_ALLOW_DOMAINS", "") or "").split(",")
        if str(x).strip()
    }
    req_domains = {str(x).strip().lower() for x in list(payload.get("domains") or []) if str(x).strip()}
    if req_domains and allowed_domains:
        blocked = sorted([x for x in req_domains if x not in allowed_domains])
        if blocked:
            return {
                "ok": False,
                "error": "domain_not_allowed",
                "blocked_domains": blocked,
                "allow_domains": sorted(list(allowed_domains)),
            }

    if _truthy(os.getenv("ESTER_OFFLINE", "1")):
        return {"ok": False, "error": "offline_network_blocked", "policy_hit": "curiosity.web.offline"}

    web_text = ""
    try:
        from bridges.internet_access import internet

        web_text = str(internet.get_digest_for_llm(query) or "")
    except Exception as exc:
        return {"ok": False, "error": "web_provider_failed", "detail": str(exc)}

    ev = _write_evidence(
        ticket_id,
        "web_search",
        {
            "schema": "ester.curiosity.evidence.v1",
            "kind": "web_search",
            "ticket_id": ticket_id,
            "query": query,
            "domains": sorted(list(req_domains)),
            "text": web_text[:12000],
            "ts": _now_ts(),
        },
    )
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "query": query,
        "chars": len(web_text),
        "evidence": {"path": ev["rel_path"], "sha256": ev["sha256"]},
    }


def _mode(value: str) -> str:
    raw = str(value or "enqueue").strip().lower()
    return "plan_only" if raw == "plan_only" else "enqueue"


def _queue_size() -> int:
    try:
        st = agent_queue.fold_state()
        return _safe_int(st.get("live_total"), 0, min_value=0)
    except Exception:
        return 0


def _pick_ticket() -> Optional[Dict[str, Any]]:
    folded = unknown_detector.fold_tickets()
    candidates = []
    for row in list(folded.get("tickets") or []):
        status = str(row.get("status") or "")
        if status not in {"open", "stale"}:
            continue
        candidates.append(dict(row))
    if not candidates:
        return None
    candidates.sort(
        key=lambda x: (
            -_safe_float(x.get("priority"), 0.0),
            _safe_int(x.get("updated_ts"), 0, min_value=0),
            str(x.get("ticket_id") or ""),
        )
    )
    return dict(candidates[0])


def _deterministic_agent_name(ticket: Dict[str, Any]) -> str:
    ticket_id = str(ticket.get("ticket_id") or "")
    query = str(ticket.get("query") or "")
    digest = _sha256_text(f"curiosity_researcher|{ticket_id}|{query}")[:12]
    return f"curiosity.researcher.{digest}"


def _ensure_agent(
    *,
    dry_run: bool,
    ticket: Dict[str, Any],
    plan: Dict[str, Any],
    allow_web: bool,
) -> Dict[str, Any]:
    name = _deterministic_agent_name(ticket)
    if dry_run:
        return {"ok": True, "agent_id": "agent_dry_curiosity", "created": False, "name": name}
    listing = agent_factory.list_agents()
    for row in list(listing.get("agents") or []):
        if str(row.get("name") or "") == name:
            return {"ok": True, "agent_id": str(row.get("agent_id") or row.get("id") or ""), "created": False, "name": name}

    allowed_actions: List[str] = []
    for step in list(plan.get("steps") or []):
        if not isinstance(step, dict):
            continue
        aid = str(step.get("action") or step.get("action_id") or "").strip()
        if aid and aid not in allowed_actions:
            allowed_actions.append(aid)

    budgets = dict(plan.get("budgets") or {})
    create_rep = agent_factory.create_agent(
        {
            "name": name,
            "goal": f"Resolve curiosity ticket {str(ticket.get('ticket_id') or '')}",
            "template_id": "curiosity_researcher",
            "allowed_actions": allowed_actions,
            "budgets": {
                "max_actions": _safe_int(budgets.get("max_steps"), len(allowed_actions) + 2, min_value=1),
                "max_work_ms": _safe_int(budgets.get("max_ms"), 2000, min_value=200),
                "window": _safe_int(budgets.get("window_sec"), 120, min_value=1),
                "est_work_ms": min(
                    _safe_int(budgets.get("max_ms"), 2000, min_value=200),
                    _safe_int(os.getenv("ESTER_CURIOSITY_EST_WORK_MS", "250"), 250, min_value=1),
                ),
            },
            "owner": "modules.curiosity.executor",
            "oracle_policy": {"enabled": bool(allow_web)},
            "comm_policy": {"enabled": False},
        }
    )
    if not bool(create_rep.get("ok")):
        return dict(create_rep if isinstance(create_rep, dict) else {"ok": False, "error": "agent_create_failed"})
    return {"ok": True, "agent_id": str(create_rep.get("agent_id") or ""), "created": True, "name": name}


def _web_policy_for_plan() -> Tuple[bool, Dict[str, Any]]:
    from modules.runtime import execution_window

    win = execution_window.current_window()
    allow = (
        _slot_effective() == "B"
        and bool(win.get("open"))
        and _truthy(os.getenv("ESTER_CURIOSITY_WEB_ENABLE", "0"))
        and _truthy(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0"))
    )
    return allow, {
        "window_open": bool(win.get("open")),
        "window_id": str(win.get("window_id") or ""),
        "policy_web_enable": _truthy(os.getenv("ESTER_CURIOSITY_WEB_ENABLE", "0")),
        "allow_outbound_network": _truthy(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")),
        "slot": _slot_effective(),
    }


def _dedupe_hit(ticket_id: str, plan_hash: str, cooldown_sec: int) -> Dict[str, Any]:
    if cooldown_sec <= 0:
        return {"hit": False}
    now = _now_ts()
    rows = unknown_detector.ticket_events()
    for row in reversed(rows):
        if str(row.get("ticket_id") or "") != str(ticket_id or ""):
            continue
        if str(row.get("event") or "") != "enqueue":
            continue
        plan = dict(row.get("plan") or {})
        if str(plan.get("plan_hash") or "") != str(plan_hash or ""):
            continue
        ts = _safe_int(row.get("ts"), 0, min_value=0)
        if ts <= 0:
            continue
        if now - ts > cooldown_sec:
            break
        enqueue = dict(row.get("enqueue") or {})
        return {"hit": True, "enqueue_id": str(enqueue.get("enqueue_id") or ""), "ts": ts}
    return {"hit": False}


def _append_manual_step_journal(
    *,
    chain_id: str,
    step: str,
    actor: str,
    intent: str,
    needs: List[str],
    budgets: Dict[str, Any],
    decision: Dict[str, Any],
) -> None:
    from modules.volition import journal as volition_journal

    allowed = bool(decision.get("allowed"))
    reason_code = str(decision.get("reason_code") or ("ALLOW" if allowed else "DENY"))
    reason = str(decision.get("reason") or "")
    slot = str(decision.get("slot") or _slot_effective())
    row = {
        "id": "vol_manual_" + _sha256_text(f"{chain_id}|{step}|{time.time()}")[:24],
        "ts": _now_ts(),
        "chain_id": str(chain_id or ""),
        "step": str(step or ""),
        "actor": str(actor or "ester"),
        "intent": str(intent or step or ""),
        "action_kind": str(step or ""),
        "allowed": allowed,
        "reason_code": reason_code,
        "reason": reason,
        "slot": slot,
        "metadata": {
            "needs": [str(x) for x in list(needs or []) if str(x).strip()],
            "budgets_snapshot": dict(budgets or {}),
            "policy_hit": str(step or ""),
        },
        "decision": ("allow" if allowed else "deny"),
        "policy_hit": str(step or ""),
        "duration_ms": _safe_int(decision.get("duration_ms"), 0, min_value=0),
    }
    try:
        volition_journal.append(row)
    except Exception:
        return


def _gate_decide(
    *,
    gate: Any,
    chain_id: str,
    step: str,
    actor: str,
    intent: str,
    needs: List[str],
    budgets: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    from modules.volition.volition_gate import VolitionContext

    decision = gate.decide(
        VolitionContext(
            chain_id=str(chain_id or ""),
            step=str(step or "action"),
            actor=str(actor or "ester"),
            intent=str(intent or step or ""),
            action_kind=str(step or ""),
            needs=list(needs or []),
            budgets=dict(budgets or {}),
            metadata=dict(metadata or {}),
        )
    )
    out = decision.to_dict()
    _append_manual_step_journal(
        chain_id=chain_id,
        step=step,
        actor=actor,
        intent=intent,
        needs=needs,
        budgets=budgets,
        decision=out,
    )
    return out


def _emit_fail_ticket(ticket: Dict[str, Any], code: str, detail: str) -> None:
    unknown_detector.append_ticket_event(
        event="fail",
        ticket_id=str(ticket.get("ticket_id") or ""),
        source=str(ticket.get("source") or "dialog"),
        query=str(ticket.get("query") or ""),
        context_text=detail,
        priority=_safe_float(ticket.get("priority"), 0.5),
        budgets=dict(ticket.get("budgets") or {}),
        status="failed",
        error={"code": str(code or "curiosity_error"), "detail": str(detail or "")},
    )


def _run_once_core(
    *,
    mode: str,
    max_work_ms: Optional[int],
    max_queue_size: Optional[int],
    cooldown_sec: Optional[int],
    dry_run: bool,
) -> Dict[str, Any]:
    from modules.thinking import action_registry
    from modules.volition.volition_gate import get_default_gate

    requested_mode = _mode(mode)
    slot = _slot_effective()
    gate = get_default_gate()
    queue_limit = _safe_int(
        (max_queue_size if max_queue_size is not None else os.getenv("ESTER_CURIOSITY_MAX_QUEUE_SIZE", "20")),
        20,
        min_value=1,
    )
    cooldown = _safe_int(
        (cooldown_sec if cooldown_sec is not None else os.getenv("ESTER_CURIOSITY_COOLDOWN_SEC", "180")),
        180,
        min_value=0,
    )
    max_ms = _safe_int(
        (max_work_ms if max_work_ms is not None else os.getenv("ESTER_CURIOSITY_MAX_WORK_MS", "2000")),
        2000,
        min_value=200,
    )

    ticket = _pick_ticket()
    if ticket is None:
        return {
            "ok": True,
            "no_work": True,
            "reason": "tickets_empty",
            "slot": slot,
            "mode": requested_mode,
            "queue_size": _queue_size(),
        }

    ticket_id = str(ticket.get("ticket_id") or "")
    chain_id = "chain_curiosity_" + _sha256_text(f"{ticket_id}|{time.time()}")[:12]
    budgets = {
        "max_work_ms": max_ms,
        "max_actions": _safe_int(os.getenv("ESTER_CURIOSITY_MAX_ACTIONS", "6"), 6, min_value=1),
        "window": _safe_int(os.getenv("ESTER_CURIOSITY_WINDOW_SEC", "120"), 120, min_value=1),
        "est_work_ms": min(max_ms, _safe_int(os.getenv("ESTER_CURIOSITY_EST_WORK_MS", "250"), 250, min_value=1)),
    }

    out: Dict[str, Any] = {
        "ok": False,
        "slot": slot,
        "mode_requested": requested_mode,
        "mode": requested_mode,
        "ticket_id": ticket_id,
        "chain_id": chain_id,
        "plan_id": "",
        "plan_hash": "",
        "agent_id": "",
        "enqueue_id": "",
        "reason": "",
        "error": "",
        "runtime_exception": False,
        "queue_size": _queue_size(),
        "queue_size_before": _queue_size(),
        "dry_run": bool(dry_run),
    }

    open_dec = _gate_decide(
        gate=gate,
        chain_id=chain_id,
        step="curiosity.ticket.open",
        actor="ester",
        intent="curiosity_ticket_open",
        needs=["curiosity.ticket.open"],
        budgets=budgets,
        metadata={"ticket_id": ticket_id, "reason": "curiosity_executor"},
    )
    if not bool(open_dec.get("allowed")):
        out["error"] = str(open_dec.get("reason_code") or "volition_denied")
        out["reason"] = "volition_denied"
        _emit_fail_ticket(ticket, out["error"], "curiosity.ticket.open denied")
        return out

    plan_dec = _gate_decide(
        gate=gate,
        chain_id=chain_id,
        step="curiosity.plan",
        actor="ester",
        intent="curiosity_plan",
        needs=["curiosity.plan"],
        budgets=budgets,
        metadata={"ticket_id": ticket_id, "reason": "curiosity_executor"},
    )
    if not bool(plan_dec.get("allowed")):
        out["error"] = str(plan_dec.get("reason_code") or "volition_denied")
        out["reason"] = "volition_denied"
        _emit_fail_ticket(ticket, out["error"], "curiosity.plan denied")
        return out

    allow_web, web_policy = _web_policy_for_plan()
    planner_mode = "web_allowed" if allow_web else "local_only"
    plan = curiosity_planner.build_plan(ticket, mode=planner_mode)
    ph = curiosity_planner.plan_hash(plan)
    plan_info = {"plan_id": str(plan.get("plan_id") or ""), "plan_hash": ph}
    out["plan_id"] = plan_info["plan_id"]
    out["plan_hash"] = ph
    out["plan_mode"] = planner_mode
    out["web_policy"] = web_policy
    unknown_detector.append_ticket_event(
        event="plan",
        ticket_id=ticket_id,
        source=str(ticket.get("source") or "dialog"),
        query=str(ticket.get("query") or ""),
        context_text=json.dumps({"planner_mode": planner_mode, "plan_id": plan_info["plan_id"]}, ensure_ascii=True),
        priority=_safe_float(ticket.get("priority"), 0.5),
        budgets=dict(ticket.get("budgets") or {}),
        status="planned",
        plan=plan_info,
    )

    queue_before = _queue_size()
    out["queue_size_before"] = queue_before
    if queue_before >= queue_limit:
        out["ok"] = True
        out["reason"] = "queue_full"
        return out

    dedupe = _dedupe_hit(ticket_id, ph, cooldown)
    if bool(dedupe.get("hit")):
        out["ok"] = True
        out["reason"] = "cooldown_dedupe"
        out["enqueue_id"] = str(dedupe.get("enqueue_id") or "")
        return out

    effective_mode = requested_mode
    if effective_mode != "plan_only" and slot == "A":
        effective_mode = "enqueue"
    out["mode"] = effective_mode
    if effective_mode == "plan_only":
        out["ok"] = True
        out["reason"] = "plan_only"
        return out

    create_dec = _gate_decide(
        gate=gate,
        chain_id=chain_id,
        step="agent.create",
        actor="ester",
        intent="curiosity_agent_create",
        needs=["agent.create"],
        budgets=budgets,
        metadata={"ticket_id": ticket_id, "template_id": "curiosity_researcher"},
    )
    if not bool(create_dec.get("allowed")):
        out["error"] = str(create_dec.get("reason_code") or "volition_denied")
        out["reason"] = "volition_denied"
        _emit_fail_ticket(ticket, out["error"], "agent.create denied")
        return out

    agent_rep = _ensure_agent(dry_run=dry_run, ticket=ticket, plan=plan, allow_web=allow_web)
    if not bool(agent_rep.get("ok")):
        out["error"] = str(agent_rep.get("error") or "agent_create_failed")
        out["reason"] = "agent_create_failed"
        _emit_fail_ticket(ticket, "agent_create_failed", out["error"])
        return out
    agent_id = str(agent_rep.get("agent_id") or "")
    out["agent_id"] = agent_id

    enqueue_dec = _gate_decide(
        gate=gate,
        chain_id=chain_id,
        step="agent.queue.enqueue",
        actor="ester",
        intent="curiosity_enqueue",
        needs=["agent.queue.enqueue"],
        budgets=budgets,
        metadata={"ticket_id": ticket_id, "plan_id": plan_info["plan_id"], "agent_id": agent_id},
    )
    if not bool(enqueue_dec.get("allowed")):
        out["error"] = str(enqueue_dec.get("reason_code") or "volition_denied")
        out["reason"] = "volition_denied"
        _emit_fail_ticket(ticket, out["error"], "agent.queue.enqueue denied")
        return out

    if dry_run:
        enqueue_rep = {"ok": True, "queue_id": "q_dry_curiosity"}
    else:
        enqueue_rep = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "plan": plan,
                "agent_id": agent_id,
                "priority": max(1, int(_safe_float(ticket.get("priority"), 0.5) * 100)),
                "challenge_sec": _safe_int(os.getenv("ESTER_CURIOSITY_CHALLENGE_SEC", "60"), 60, min_value=0),
                "actor": "ester",
                "reason": f"curiosity_enqueue:{ticket_id}",
            },
        )
    if not bool((enqueue_rep or {}).get("ok")):
        out["error"] = str((enqueue_rep or {}).get("error") or "enqueue_failed")
        out["reason"] = "enqueue_failed"
        _emit_fail_ticket(ticket, "enqueue_failed", out["error"])
        return out

    enqueue_id = str((enqueue_rep or {}).get("queue_id") or "")
    out["enqueue_id"] = enqueue_id
    out["queue_size"] = _queue_size()
    unknown_detector.append_ticket_event(
        event="enqueue",
        ticket_id=ticket_id,
        source=str(ticket.get("source") or "dialog"),
        query=str(ticket.get("query") or ""),
        context_text=json.dumps({"enqueue_id": enqueue_id, "agent_id": agent_id}, ensure_ascii=True),
        priority=_safe_float(ticket.get("priority"), 0.5),
        budgets=dict(ticket.get("budgets") or {}),
        status="enqueued",
        plan=plan_info,
        enqueue={"enqueue_id": enqueue_id, "agent_id": agent_id, "queue_size": _queue_size()},
    )
    out["ok"] = True
    out["reason"] = "enqueued"
    return out


def run_once(
    *,
    mode: str = "enqueue",
    max_work_ms: Optional[int] = None,
    max_queue_size: Optional[int] = None,
    cooldown_sec: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    global _SLOTB_ERR_STREAK, _SLOTB_DISABLED, _SLOTB_LAST_FALLBACK_REASON, _SLOTB_LAST_FALLBACK_TS

    try:
        rep = _run_once_core(
            mode=mode,
            max_work_ms=max_work_ms,
            max_queue_size=max_queue_size,
            cooldown_sec=cooldown_sec,
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        rep = {
            "ok": False,
            "error": "slot_runtime_error",
            "detail": f"{exc.__class__.__name__}: {exc}",
            "runtime_exception": True,
            "slot": _slot_effective(),
            "mode": _mode(mode),
            "ticket_id": "",
        }

    slot = _slot_raw()
    runtime_exc = bool(rep.get("runtime_exception"))
    if bool(rep.get("ok")):
        _SLOTB_ERR_STREAK = 0
        return rep

    if slot == "B" and runtime_exc:
        _SLOTB_ERR_STREAK += 1
        if _SLOTB_ERR_STREAK >= _slot_b_fail_max():
            _SLOTB_DISABLED = True
            _SLOTB_LAST_FALLBACK_REASON = str(rep.get("detail") or rep.get("error") or "slot_b_auto_rollback")
            _SLOTB_LAST_FALLBACK_TS = _now_ts()
            ticket_id = str(rep.get("ticket_id") or "").strip()
            if ticket_id:
                ticket = _ticket_meta(ticket_id)
                _emit_fail_ticket(
                    ticket,
                    "slot_b_auto_rollback",
                    str(rep.get("detail") or rep.get("error") or "slot_b_auto_rollback"),
                )
            rep["fallback"] = {
                "trigger": "slot_b_auto_rollback",
                "streak": _SLOTB_ERR_STREAK,
                "slot_effective": "A",
            }
    return rep


def runtime_state() -> Dict[str, Any]:
    return {
        "ok": True,
        "slot_raw": _slot_raw(),
        "slot_effective": _slot_effective(),
        "slot_b_disabled": bool(_SLOTB_DISABLED),
        "slot_b_err_streak": int(_SLOTB_ERR_STREAK),
        "slot_b_fail_max": int(_slot_b_fail_max()),
        "slot_b_last_fallback_reason": str(_SLOTB_LAST_FALLBACK_REASON or ""),
        "slot_b_last_fallback_ts": int(_SLOTB_LAST_FALLBACK_TS or 0),
    }


__all__ = [
    "run_once",
    "runtime_state",
    "action_local_search",
    "action_local_extract",
    "action_local_crosscheck",
    "action_crystallize_fact",
    "action_crystallize_negative",
    "action_close_ticket",
    "action_web_search",
]
