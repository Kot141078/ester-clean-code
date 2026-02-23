# -*- coding: utf-8 -*-
"""
messaging/wa_templates.py — otpravka i predprosmotr WhatsApp shablonnykh soobscheniy (Cloud API).

MOSTY:
- (Yavnyy) preview_template(name, variables) — render teksta iz YAML-konfiga dlya predprosmotra v adminke.
- (Skrytyy #1) Rasshirennyy YAML: polya `body` i `variables` (opisanie peremennykh) dlya lokalnogo prevyu.
- (Skrytyy #2) DRYRUN: DEV_DRYRUN=1 vozvraschaet payload vmesto realnoy otpravki.

ZEMNOY ABZATs:
Operator vidit, chto uydet adresatu, prezhde chem nazhat «Otpravit» — ekonomit vremya i snimaet oshibki v tekstakh.

# c=a+b
"""
from __future__ import annotations

import json, os, re
from typing import Any, Dict, List, Optional

from messaging.whatsapp_adapter import WhatsAppAdapter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_RE_PL = re.compile(r"\{\{\s*(\d+)\s*\}\}")

def _load_catalog() -> Dict[str, Any]:
    catalog_path = os.getenv("WA_TEMPLATES_CONFIG", "config/wa_templates.yaml")
    try:
        import yaml  # type: ignore
        with open(catalog_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def list_templates() -> List[str]:
    return list((_load_catalog().get("templates") or {}).keys())

def _build_template_payload(name: str, to_msisdn: str, variables: List[str]) -> Dict[str, Any]:
    cat = _load_catalog().get("templates") or {}
    tpl = cat.get(name) or {}
    lang = os.getenv("WA_TEMPLATE_LANG", tpl.get("lang","ru"))
    ns = os.getenv("WA_TEMPLATE_NAMESPACE", tpl.get("namespace",""))
    comps = []
    if variables:
        comps = [{
            "type":"body",
            "parameters":[{"type":"text", "text": v} for v in variables]
        }]
    return {
        "messaging_product": "whatsapp",
        "to": to_msisdn,
        "type": "template",
        "template": {
            "name": name,
            "language": {"code": lang},
            **({"namespace": ns} if ns else {}),
            **({"components": comps} if comps else {})
        }
    }

def _render_body(body: str, variables: List[str]) -> str:
    def repl(m):
        idx = int(m.group(1)) - 1
        return (variables[idx] if 0 <= idx < len(variables) else f"{{{{{m.group(1)}}}}}")
    return _RE_PL.sub(repl, body)

def preview_template(name: str, variables: Optional[List[str]] = None) -> Optional[str]:
    cat = _load_catalog().get("templates") or {}
    tpl = cat.get(name)
    if not tpl:
        return None
    body = (tpl.get("body") or "").strip()
    if not body:
        return None
    return _render_body(body, variables or [])

def send_template(to_msisdn: str, name: str, variables: Optional[List[str]] = None) -> Dict[str, Any]:
    payload = _build_template_payload(name, to_msisdn, variables or [])
    if os.getenv("DEV_DRYRUN","0") == "1":
        return {"ok": True, "status": 200, "body": json.dumps(payload, ensure_ascii=False)}
    a = WhatsAppAdapter()
    url = f"https://graph.facebook.com/v21.0/{a.phone_id}/messages"
    from messaging.whatsapp_adapter import _post  # reuse
    code, body = _post(url, payload, a.token)
    return {"ok": code in (200,201), "status": code, "body": body}

def send_template_from_catalog(to_msisdn: str, name: str, variables: Optional[List[str]] = None) -> Dict[str, Any]:
    return send_template(to_msisdn, name, variables or [])
