# -*- coding: utf-8 -*-
"""
messaging/email_compose.py — planirovanie i generatsiya pisem (tema/tekst/HTML) s A/B rezhimom.

MOSTY:
- (Yavnyy) compose_email(keys, intent, context, kind_hint) → {"subject","text","html","style","trace"}.
- (Skrytyy #1) Rezhim A (evristika) — bystryy i determinirovannyy; rezhim B — most k LLM (EMAIL_LLM_PROVIDER), s avtokatbekom na A.
- (Skrytyy #2) Profile poluchateley podtyagivaetsya cherez roles.store (contact_key→agent_id), usrednyaetsya kak v messaging.styler.

ZEMNOY ABZATs:
Pisma — eto ne «magiya teksta», a struktura: tema, privetstvie, sut, deystviya, srok, podpis. Ester vybiraet stil i zapolnyaet karkas.

# c=a+b
"""
from __future__ import annotations

import os, re, html, importlib
from typing import Any, Dict, List, Optional, Tuple
from roles.store import get_agent_by_key, get_profile
from messaging.email_styles import pick_style
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _aggregate_profiles(keys: List[str]) -> Tuple[Dict[str,float], List[str]]:
    acc: Dict[str,float] = {}; labs: set[str] = set(); n=0
    for k in keys:
        ag = get_agent_by_key(k)
        if not ag: continue
        prof = get_profile(ag)
        if not prof: continue
        for d,v in (prof.get("vector") or {}).items():
            acc[d] = acc.get(d,0.0) + float(v)
        for l in (prof.get("labels") or []):
            labs.add(str(l))
        n += 1
    if n>0:
        for d in list(acc.keys()):
            acc[d] /= n
    return acc, sorted(list(labs))

def _first_sentence(s: str, limit: int = 60) -> str:
    s = re.split(r"[.!?]\s", s.strip())[0]
    if len(s) > limit:
        s = s[:limit-1].rstrip() + "…"
    return s

def _render_heuristic(intent: str, style: Dict[str,Any], ctx: Dict[str,Any]) -> Dict[str,str]:
    subj = (style.get("subject_prefix","") or "") + _first_sentence(intent, limit=72)
    greet = style.get("greeting","Zdravstvuyte")
    sign = style.get("signoff","")
    # Telo: prichina → detali → deystvie → srok
    parts = []
    reason = intent.strip()
    details = ctx.get("details") or ctx.get("context") or ""
    action = ctx.get("action") or ctx.get("cta") or "Dayte znat, pozhaluysta, mozhno li tak sdelat."
    deadline = ctx.get("deadline")
    if style.get("formality",0.6) >= 0.8:
        opener = f"{greet}."
    else:
        opener = f"{greet}!"

    parts.append(opener + " " + reason)
    if details:
        parts.append(str(details))
    if deadline:
        parts.append(f"Srok: {deadline}.")
    parts.append(action)

    if sign:
        parts.append(sign + ", " + os.getenv("EMAIL_DISPLAY_NAME","E."))
    text = "\n\n".join(parts)

    # HTML-versiya
    body_html = "".join(f"<p>{html.escape(p)}</p>" for p in parts[:-1])
    if sign:
        body_html += f"<p>{html.escape(sign)},<br>{html.escape(os.getenv('EMAIL_DISPLAY_NAME','E.'))}</p>"
    else:
        body_html += "<p>&nbsp;</p>"
    return {"subject": subj, "text": text, "html": body_html}

def _try_llm(intent: str, style: Dict[str,Any], ctx: Dict[str,Any]) -> Optional[Dict[str,str]]:
    if (os.getenv("EMAIL_INFER_MODE","A").upper() != "B"):
        return None
    spec = os.getenv("EMAIL_LLM_PROVIDER","").strip()
    if not spec:
        return None
    try:
        mod, fn = spec.split(":",1)
        f = getattr(importlib.import_module(mod), fn)
        res = f({"intent":intent, "style":style, "context":ctx})
        if isinstance(res, dict) and "subject" in res and ("text" in res or "html" in res):
            # normalizuem
            subj = str(res.get("subject") or "").strip()
            text = str(res.get("text") or "")
            html_s = str(res.get("html") or "")
            return {"subject": subj, "text": text, "html": html_s}
        return None
    except Exception:
        return None

def compose_email(keys: List[str], intent: str, context: Dict[str,Any] | None = None, kind_hint: Optional[str] = None) -> Dict[str,Any]:
    ctx = context or {}
    vec, labels = _aggregate_profiles(keys)
    style = pick_style(vec, labels, kind_hint, signature_opt=os.getenv("EMAIL_SIGNATURE_OPT","soft"))
    # rezhim B → A (avtokatbek)
    res = _try_llm(intent, style, ctx)
    trace = []
    if res is None:
        res = _render_heuristic(intent, style, ctx)
        trace.append("mode=A:heuristic_template")
    else:
        trace.append("mode=B:llm_provider")

    return {"subject": res["subject"], "text": res["text"], "html": res["html"], "style": style,
            "trace": trace, "labels": labels, "vector": vec}