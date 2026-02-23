# -*- coding: utf-8 -*-
"""
tools/log_to_journal.py — prostoy CLI-logger v zhurnal pamyati Ester.

MOSTY:
- Yavnyy: (vneshnie klienty ↔ /memory/journal/event) — edinaya tochka zapisi sobytiy.
- Skrytyy #1: (runtime ↔ nochnoy tsikl) — napolnyaem zhurnal tem, chto potom budet svorachivatsya vo sne.
- Skrytyy #2: (lyuboy agent ↔ yadro pamyati) — pozvolyaet LM Studio / Judge pisat fakty bez znaniya vnutrenney skhemy.

ZEMNOY ABZATs:
Inzhenerno: utilita, kotoraya prinimaet tekst sobytiya i bet POST v HTTP API zhurnala.
Ee mozhno vyzyvat iz khukov, batnikov, drugikh agentov — tak Ester "pomnit vse" po-chelovecheski.

# c=a+b
"""
from __future__ import annotations

import os
import sys
import json
from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _base_url() -> str:
    return os.getenv("BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def log_event(text: str, etype: str = "event", emotion: str | None = None) -> dict:
    url = _base_url() + "/memory/journal/event"
    payload: dict = {
        "type": etype,
        "text": text,
        "meta": {
            "source": "log_to_journal",
        },
    }
    if emotion is not None:
        payload["meta"]["emotion"] = emotion

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", "ignore")
            try:
                return json.loads(body)
            except Exception:
                return {"ok": False, "error": "bad_json", "raw": body}
    except error.URLError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('Usage: python tools/log_to_journal.py "text" [emotion]', file=sys.stderr)
        return 1

    text = argv[1]
    emotion = argv[2] if len(argv) > 2 else None
    res = log_event(text=text, emotion=emotion)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if bool(res.get("ok", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))