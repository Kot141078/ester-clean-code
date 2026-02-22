# -*- coding: utf-8 -*-
"""
Deterministic image captioning baseline.

Optional enrichments:
- PIL/Pillow for width/height/format metadata
- local vision provider (localhost only, gated by modules.net_guard)
"""
from __future__ import annotations

import base64
import json
import os
from io import BytesIO
from typing import Any, Dict, Optional
from urllib import request as urlrequest

from modules.net_guard import allow_network, deny_payload, is_local_url


def _guess_mime(name: str, data: bytes) -> str:
    low = str(name or "").lower()
    if low.endswith(".png") or data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if low.endswith(".jpg") or low.endswith(".jpeg") or data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if low.endswith(".gif"):
        return "image/gif"
    if low.endswith(".webp"):
        return "image/webp"
    if low.endswith(".bmp"):
        return "image/bmp"
    return "application/octet-stream"


def _extract_pil_meta(data: bytes) -> Dict[str, Any]:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return {}
    try:
        with Image.open(BytesIO(data)) as img:
            return {
                "width": int(img.width),
                "height": int(img.height),
                "format": str(img.format or "").lower(),
            }
    except Exception:
        return {}


def _fallback_caption(name: str, data: bytes, meta: Dict[str, Any]) -> str:
    base = os.path.basename(str(name or "image"))
    ext = os.path.splitext(base)[1].lower().lstrip(".") or "bin"
    size = len(data or b"")
    wh = ""
    if meta.get("width") and meta.get("height"):
        wh = f", {meta['width']}x{meta['height']}"
    return f"{base}: {ext}, {size} bytes{wh}"


def _call_local_provider(url: str, name: str, data: bytes) -> Optional[str]:
    if not is_local_url(url):
        return None
    if not allow_network(url):
        return None
    payload = {
        "name": str(name or "image"),
        "data_b64": base64.b64encode(data).decode("ascii"),
    }
    req = urlrequest.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:  # nosec B310 (explicit guard above)
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    try:
        doc = json.loads(raw)
    except Exception:
        return None
    cap = str(doc.get("caption") or "").strip()
    return cap or None


def caption_image(name: str, data: bytes) -> Dict[str, Any]:
    mime = _guess_mime(name, data)
    meta = _extract_pil_meta(data)
    caption = _fallback_caption(name, data, meta)

    provider_url = (os.getenv("ESTER_LOCAL_VISION_URL") or "").strip()
    provider_used = False
    provider_denied = False
    if provider_url:
        provider_used = True
        if allow_network(provider_url):
            cap = _call_local_provider(provider_url, name, data)
            if cap:
                caption = cap
        else:
            provider_denied = True

    res: Dict[str, Any] = {
        "ok": True,
        "caption": caption,
        "path": str(name or ""),
        "mime": mime,
    }
    if meta:
        res["meta"] = meta
    if provider_used:
        res["provider"] = {"url": provider_url, "denied": provider_denied}
        if provider_denied:
            res["provider_error"] = deny_payload(provider_url, target="local_vision_provider")
    return res
