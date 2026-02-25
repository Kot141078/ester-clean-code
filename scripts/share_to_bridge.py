# -*- coding: utf-8 -*-
"""scripts/share_to_bridge.py - CLI dlya otpravki teksta/HTML v Share Bridge (/share/capture).
Sovmestimo s kanonom, ne trebuet vneshnikh bibliotek.
Primery:
  echo "Hello Ester" | python scripts/share_to_bridge.py --title "Zametka"
  python scripts/share_to_bridge.py --file page.html --url https://example.com --tags notes,web
  python scripts/share_to_bridge.py --batch items.json # [{"title":"t","text":"...","tags":["x"]}, ...]
ENV:
  BRIDGE_BASE (by default http://127.0.0.1:18081)"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional
from urllib import request as ureq
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BRIDGE = (os.getenv("BRIDGE_BASE") or "http://127.0.0.1:18081").rstrip("/")


def _read_stdin() -> str:
    if sys.stdin and not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _post_json(url: str, payload: Any) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = ureq.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with ureq.urlopen(req, timeout=30) as resp:  # nosec - CLI instrument
        raw = resp.read().decode("utf-8", "ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw, "status": getattr(resp, "status", None)}


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Ester Share Bridge CLI")
    ap.add_argument("--title", help="Zagolovok", default="untitled")
    ap.add_argument("--url", help="Istochnik URL", default="")
    ap.add_argument("--tags", help="List of tags separated by commas", default="")
    ap.add_argument("--note", help="Zametka", default=None)
    ap.add_argument("--file", help="Put k faylu (html/txt)", default=None)
    ap.add_argument(
        "--batch", help="JSON-fayl s massivom elementov", default=None
    )
    args = ap.parse_args(argv)

    if args.batch:
        # Batch: v fayle JSON — massiv obektov {title, html|text, url?, tags?}
        items = json.loads(open(args.batch, "r", encoding="utf-8").read())
        if not isinstance(items, list):
            print(
                "The JSION batch must contain an array of objects",
                file=sys.stderr,
            )
            return 2
        # normalizatsiya
        for it in items:
            it.setdefault("title", "untitled")
            it.setdefault("url", "")
            it.setdefault("tags", [])
            it.setdefault("note", None)
            if "html" not in it and "text" not in it:
                it["text"] = ""
        resp = _post_json(BRIDGE + "/share/capture", {"items": items})
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0

    # Single sending: reading stdin or file
    html = ""
    text = ""
    if args.file:
        data = open(args.file, "rb").read()
        try:
            # rough check: if there is <html, we count as html
            s = data.decode("utf-8", "ignore")
            if "<html" in s.lower() or "<!doctype" in s.lower():
                html = s
            else:
                text = s
        except Exception:
            text = ""
    else:
        std = _read_stdin()
        if std.strip():
            # if the stdin contains HTML tags, we will send it as HTML
            low = std.lower()
            if "<html" in low or "<!doctype" in low or "<body" in low:
                html = std
            else:
                text = std

    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    payload = {
        "url": args.url or "",
        "title": args.title or "untitled",
        "html": html,
        "text": text,
        "selection": "",
        "tags": tags,
        "note": args.note,
    }
    resp = _post_json(BRIDGE + "/share/capture", payload)
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))