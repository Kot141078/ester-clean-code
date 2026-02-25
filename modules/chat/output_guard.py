# -*- coding: utf-8 -*-
from __future__ import annotations

"""modules/chat/output_guard.py

Myagkiy predokhranitel na urovne HTTP-otvetov:
- lovit tipichnye zatsiklivaniya i bessmyslennye povtory v polyakh answer/text/content/output,
- ne raskryvaet chain-of-thought,
- ne lomaet ne-JSON otvety.

MOSTY:
- Yavnyy: LLM-vykhod ↔ UI — srezaem musor, ostavlyaem smysl.
- Skrytyy #1: Infoteoriya ↔ praktika — nizkaya entropiya/povtoryaemost kak signal degradatsii.
- Skrytyy #2: Kibernetika ↔ bezopasnost - predokhranitel kak kontur stabilizatsii.

ZEMNOY ABZATs:
Kak termostat na kotle: on ne delaet vodu umnoy, no ne daet ey vykipet do sukha."""

import json
import re
import os
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


MAX_CHARS = int(os.environ.get("ESTER_GUARD_MAX_CHARS", "6000"))
MAX_REPEAT_RATIO = float(os.environ.get("ESTER_GUARD_MAX_REPEAT_RATIO", "0.55"))
MIN_LEN_TO_CHECK = int(os.environ.get("ESTER_GUARD_MIN_LEN", "800"))


def _strip_spaces(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()


def _repeat_ratio(s: str) -> float:
    """Ochen grubaya otsenka “zatiklennosti”:
    - normalizuem probely,
    - schitaem frequency 3-gramm,
    - esli kakaya-to 3-gramma vstrechaetsya slishkom chasto - znachit, model zaela."""
    s = _strip_spaces(s)
    words = s.split()
    if len(words) < 60:
        return 0.0
    grams = []
    for i in range(len(words) - 2):
        grams.append(" ".join(words[i:i+3]).lower())
    if not grams:
        return 0.0
    freq: Dict[str, int] = {}
    for g in grams:
        freq[g] = freq.get(g, 0) + 1
    top = max(freq.values())
    return top / max(1, len(grams))


def _guard_text(text: str) -> Optional[str]:
    """Returns *new* text if trimmed/marked, None otherwise."""
    if not isinstance(text, str):
        return None
    if len(text) < MIN_LEN_TO_CHECK:
        return None

    rr = _repeat_ratio(text)
    if rr >= MAX_REPEAT_RATIO:
        cut = min(len(text), 1800)
        return text[:cut].rstrip() + "yutput-guard cut off: looped repeat detected."

    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS].rstrip() + "\n\n[output-guard] obrezano: slishkom dlinnyy vyvod."

    return None


def _try_json(resp) -> Optional[Dict[str, Any]]:
    try:
        raw = resp.get_data(as_text=True)
    except Exception:
        return None
    if not raw:
        return None
    try:
        j = json.loads(raw)
    except Exception:
        return None
    if isinstance(j, dict):
        return j
    return None


def _install_guard(app) -> None:
    @app.after_request
    def _ester_output_guard(resp):
        try:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "application/json" not in ctype:
                return resp

            obj = _try_json(resp)
            if not isinstance(obj, dict):
                return resp

            changed = False

            def _patch_dict(d: Dict[str, Any]) -> None:
                nonlocal changed
                for key in ("answer", "text", "content", "output"):
                    if key in d and isinstance(d.get(key), str):
                        new_text = _guard_text(d[key])
                        if new_text is not None:
                            d[key] = new_text
                            changed = True

            _patch_dict(obj)
            if isinstance(obj.get("data"), dict):
                _patch_dict(obj["data"])

            if changed:
                payload = json.dumps(obj, ensure_ascii=False)
                b = payload.encode("utf-8")
                resp.set_data(b)
                resp.headers["Content-Length"] = str(len(b))
                resp.headers["X-Ester-OutputGuard"] = "1"

            return resp
        except Exception:
            return resp

    print("[ester-output-guard] installed")


def register(app) -> None:
    """Entry point for autoload_modules_fs() in app.
    It doesn't return anything, it just adds an after_request hook."""
    _install_guard(app)