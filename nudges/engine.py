# -*- coding: utf-8 -*-
"""
nudges/engine.py — SLA-tsepochki + eskalatsii (NUDGES_ESC_CHAIN) + bazovye pravila.

MOSTY:
- (Yavnyy) NUDGES_ESC_CHAIN="manager:0,oncall:15,legal:60" daet uvedomleniya tegam cherez minuty posle dedlayna.
- (Skrytyy #1) Osnovnaya SLA-tsep (NUDGES_SLA_CHAIN) prodolzhaet rabotat dlya aktorov; eskalatsii — otdelnye due dlya tegov.
- (Skrytyy #2) V otsutstvie ENV berem znacheniya iz config/nudges.yaml (intent_tpl_escalation), bez lomki proshloy logiki.

ZEMNOY ABZATs:
Snachala berezhno napominaem ispolnitelyu, a esli zadacha «gorit» — akkuratno zovem menedzhera/onkolla v nuzhnyy moment.

# c=a+b
"""
from __future__ import annotations

import os, time
from typing import Any, Dict, List

from nudges.store import get_contact_key, get_escalation
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

_DEFAULT_CFG = {
    "rules": {
        "AssignmentPlanned": {
            "kind": "friend",
            "intent_tpl": "Napominayu pro zadachu «{summary}». Dedlayn cherez ~{mins} min. Vse ok?",
            "sla_soon_min": int(os.getenv("NUDGES_SLA_SOON_MIN", "120")),
            "intent_tpl_escalation": os.getenv("NUDGES_ESC_INTENT", "Prosrochka po «{summary}». Nuzhna pomosch dlya razblokirovki.")
        },
        "OutcomeReported": {
            "kind": "neutral",
            "intent_tpl": "Spasibo za rezultat po «{summary}». Korotko: {outcome}. Nuzhen post-mortem?",
        },
        "AssignmentRequested": {
            "kind": "neutral",
            "intent_tpl": "Prinyal zapros «{summary}». Vernus s planom v blizhayshee vremya.",
        }
    }
}

def _load_cfg() -> Dict[str, Any]:
    path = os.getenv("NUDGES_CONFIG", "config/nudges.yaml")
    if yaml is None:
        return _DEFAULT_CFG
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else _DEFAULT_CFG
    except Exception:
        return _DEFAULT_CFG

def _as_list(x) -> List[Dict[str, Any]]:
    if not x: return []
    if isinstance(x, list): return x
    return [x]

def _sla_chain_minutes() -> List[int]:
    raw = (os.getenv("NUDGES_SLA_CHAIN") or "").strip()
    if not raw:
        return []
    out: List[int] = []
    for t in raw.split(","):
        t = t.strip()
        if not t: continue
        try: out.append(int(t))
        except: pass
    return out

def _esc_chain() -> List[tuple[str,int]]:
    """
    Vozvraschaet spisok (tag, minutes_after_deadline) iz NUDGES_ESC_CHAIN.
    """
    raw = (os.getenv("NUDGES_ESC_CHAIN") or "").strip()
    out: List[tuple[str,int]] = []
    if not raw: return out
    for token in raw.split(","):
        token = token.strip()
        if not token or ":" not in token: continue
        tag, off = token.split(":",1)
        try:
            out.append((tag.strip(), int(off.strip())))
        except:
            continue
    return out


def _esc_tags() -> List[str]:
    raw = (os.getenv("NUDGES_ESCALATE_TAGS") or "").strip()
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]

def plan(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    cfg = _load_cfg()
    evt_type = event.get("event_type")
    payload = event.get("payload") or {}
    ts = float(event.get("ts") or time.time())
    out: List[Dict[str, Any]] = []
    max_per = int(os.getenv("NUDGES_MAX_PER_EVENT", "5") or "5")

    if evt_type == "AssignmentPlanned":
        rule = (cfg.get("rules") or {}).get("AssignmentPlanned") or {}
        kind = str(rule.get("kind", "friend"))
        deadline = float(payload.get("deadline_ts") or 0.0)
        summary = str(payload.get("summary") or "")
        actors = _as_list(payload.get("actors"))

        if deadline > 0:
            now = time.time()
            # 1) SLA-tsepochka dlya aktorov
            chain = _sla_chain_minutes()
            if chain:
                for a in actors:
                    key = get_contact_key(str(a.get("agent_id")))
                    if not key: continue
                    for m in chain:
                        due = (deadline - m*60) if m >= 0 else (deadline + abs(m)*60)
                        if due < now: due = now + 1
                        mins_to_deadline = max(1, int((deadline - now)/60.0))
                        intent = str(rule.get("intent_tpl","")).format(summary=summary, mins=mins_to_deadline)
                        out.append({"due_ts": due, "key": key, "kind": kind, "intent": intent})
                        if len(out) >= max_per: return out
            else:
                # folbek: odinochnoe napominanie, esli blizko
                soon_min = int(rule.get("sla_soon_min", 120))
                if (deadline - now) <= soon_min*60:
                    mins = max(1, int((deadline - now)/60.0))
                    for a in actors:
                        key = get_contact_key(str(a.get("agent_id"))); 
                        if not key: continue
                        intent = str(rule.get("intent_tpl","")).format(summary=summary, mins=mins)
                        out.append({"due_ts": ts + 1, "key": key, "kind": kind, "intent": intent})
                        if len(out) >= max_per: return out

            # 1b) Legacy escalation tags: when task is overdue, notify responsible tags immediately.
            if now > deadline:
                esc_tpl = str(
                    rule.get(
                        "intent_tpl_escalation",
                        os.getenv(
                            "NUDGES_ESC_INTENT",
                            "Prosrochka po «{summary}». Nuzhna pomosch dlya razblokirovki.",
                        ),
                    )
                )
                mins_over = max(1, int((now - deadline) / 60.0))
                for tag in _esc_tags():
                    key = get_escalation(tag)
                    if not key:
                        continue
                    intent = esc_tpl.format(summary=summary, mins_over=mins_over)
                    out.append({"due_ts": now + 1, "key": key, "kind": "lawyer", "intent": intent})
                    if len(out) >= max_per:
                        return out

            # 2) Eskalatsionnaya tsepochka po dedlaynu
            esc_tpl = str(rule.get("intent_tpl_escalation",
                                   os.getenv("NUDGES_ESC_INTENT","Prosrochka po «{summary}». Nuzhna pomosch dlya razblokirovki.")))
            for tag, minutes_after in _esc_chain():
                key = get_escalation(tag)
                if not key: continue
                due = deadline + max(0, minutes_after)*60
                if due < now: due = now + 1
                intent = esc_tpl.format(summary=summary, mins_over=max(1, int((now - deadline)/60.0)))
                out.append({"due_ts": due, "key": key, "kind": "lawyer", "intent": intent})
                if len(out) >= max_per: return out

    elif evt_type == "OutcomeReported":
        rule = (cfg.get("rules") or {}).get("OutcomeReported") or {}
        kind = str(rule.get("kind","neutral"))
        summary = str(payload.get("summary") or "")
        outcome = str(payload.get("outcome") or "uspeshno")
        for a in _as_list(payload.get("actors")):
            key = get_contact_key(str(a.get("agent_id")))
            if not key: continue
            intent = str(rule.get("intent_tpl","")).format(summary=summary, outcome=outcome)
            out.append({"due_ts": ts + 1, "key": key, "kind": kind, "intent": intent})
            if len(out) >= max_per: return out

    elif evt_type == "AssignmentRequested":
        rule = (cfg.get("rules") or {}).get("AssignmentRequested") or {}
        kind = str(rule.get("kind","neutral"))
        summary = str(payload.get("summary") or "")
        for a in _as_list(payload.get("actors")):
            key = get_contact_key(str(a.get("agent_id"))); 
            if not key: continue
            intent = str(rule.get("intent_tpl","")).format(summary=summary)
            out.append({"due_ts": ts + 1, "key": key, "kind": kind, "intent": intent})
            if len(out) >= max_per: return out

    else:
        rule = (cfg.get("rules") or {}).get(evt_type or "") or {}
        if rule:
            kind = str(rule.get("kind","neutral"))
            intent_tpl = str(rule.get("intent_tpl",""))
            for a in _as_list(payload.get("actors")):
                key = get_contact_key(str(a.get("agent_id"))); 
                if not key: continue
                intent = intent_tpl.format(**payload)
                out.append({"due_ts": ts + 1, "key": key, "kind": kind, "intent": intent})
                if len(out) >= max_per: return out

    return out[:max_per]
