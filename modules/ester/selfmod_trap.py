import json
import os
import re
from typing import Any, Dict, List, Tuple, Optional

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


SELFMOD_ENDPOINT = os.getenv(
    "ESTER_SELFMOD_PROPOSE_GUARDED_URL",
    "http://127.0.0.1:8080/ester/selfmod/propose_guarded",
)

# Belyy spisok klassov dlya reason
ALLOWED_REASON_CLASSES = {
    "helper",
    "log",
    "profile",
    "selfmap",
    "safety",
    "net_bridge",
    "journal",
    "notes",
}

# Razreshennyy koren dlya faylov
ALLOWED_PREFIX = "modules/ester/"


def _parse_json_maybe(text: str) -> Optional[Dict[str, Any]]:
    """
    Pytaetsya rasparsit tekst kak JSON-obekt.
    Esli ne poluchaetsya — vozvraschaet None.
    """
    text = text.strip()
    if not text:
        return None

    # Esli model zachem-to obernula v troynye kavychki ili ```json
    if text.startswith("```"):
        # ubiraem formatirovanie
        text = re.sub(r"^```[a-zA-Z0-9]*", "", text.strip())
        text = re.sub(r"```$", "", text.strip())

    try:
        obj = json.loads(text)
    except Exception:
        return None

    if not isinstance(obj, dict):
        return None

    return obj


def _validate_selfmod_payload(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Proveryaet, chto JSON deystvitelno yavlyaetsya volevym selfmod-zaprosom Ester
    po nashemu protokolu.
    Vozvraschaet (ok, reason).
    """
    # source
    if data.get("source") != "ester":
        return False, "source_not_ester"

    # reason
    reason = data.get("reason")
    if not isinstance(reason, str):
        return False, "reason_not_str"
    if not reason.startswith("ester_will::"):
        return False, "reason_prefix_invalid"

    # razbor ester_will::<class>::<slug>
    parts = reason.split("::", 2)
    if len(parts) != 3:
        return False, "reason_format_invalid"
    _, cls, slug = parts
    if cls not in ALLOWED_REASON_CLASSES:
        return False, f"reason_class_not_allowed:{cls}"
    if not slug or not re.match(r"^[a-z0-9_]+$", slug):
        return False, "reason_slug_invalid"

    # changes
    changes = data.get("changes")
    if not isinstance(changes, list) or not changes:
        return False, "changes_missing"

    for ch in changes:
        if not isinstance(ch, dict):
            return False, "change_not_object"

        path = ch.get("path")
        content = ch.get("content")

        if not isinstance(path, str) or not isinstance(content, str):
            return False, "path_or_content_not_str"

        if not path.startswith(ALLOWED_PREFIX):
            return False, f"path_not_allowed:{path}"

        # bazovaya strakhovka: tolko .py i bez podlostey
        if not path.endswith(".py"):
            return False, f"path_not_py:{path}"

        # nikakikh popytok lezt vverkh
        if ".." in path:
            return False, f"path_traversal:{path}"

    return True, "ok"


def detect_selfmod_request(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Esli raw_text — validnyy selfmod JSON ot Ester, vozvraschaet etot JSON.
    Inache None.
    """
    data = _parse_json_maybe(raw_text)
    if data is None:
        return None

    ok, _ = _validate_selfmod_payload(data)
    if not ok:
        return None

    return data


def submit_selfmod_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sinkhronno otpravlyaet payload v /ester/selfmod/propose_guarded.
    Nikakikh fonovykh zadach, odin yavnyy vyzov.
    """
    try:
        resp = requests.post(
            SELFMOD_ENDPOINT,
            json=payload,
            timeout=10,
        )
    except Exception as e:
        return {
            "ok": False,
            "error": "request_failed",
            "detail": str(e),
        }

    try:
        data = resp.json()
    except Exception:
        return {
            "ok": False,
            "error": "invalid_json_response",
            "status_code": resp.status_code,
            "text": resp.text[:2000],
        }

    return {
        "ok": bool(data.get("ok", False)),
        "status_code": resp.status_code,
        "raw": data,
    }


def handle_ester_reply_maybe_selfmod(
    reply_text: str,
    auto_submit: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Glavnaya «lovushka».

    1. Proveryaet, yavlyaetsya li otvet Ester selfmod-JSON po protokolu.
    2. Esli net — vozvraschaet None.
    3. Esli da:
       - esli auto_submit=True — shlet v propose_guarded i vozvraschaet rezultat.
       - esli auto_submit=False — tolko vozvraschaet payload dlya UI/operatora.

    Vozvraschaemyy format:
    {
      "kind": "selfmod_proposal",
      "payload": { ... },
      "submitted": bool,
      "result": { ... } | None
    }
    """
    payload = detect_selfmod_request(reply_text)
    if not payload:
        return None

    if not auto_submit:
        return {
            "kind": "selfmod_proposal",
            "payload": payload,
            "submitted": False,
            "result": None,
        }

    result = submit_selfmod_request(payload)

    return {
        "kind": "selfmod_proposal",
        "payload": payload,
        "submitted": True,
        "result": result,
    }