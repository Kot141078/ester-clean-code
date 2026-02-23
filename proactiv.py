# -*- coding: utf-8 -*-
"""proactiv.py — klient dlya /proactive (Proactive Suggestions) v Ester.

Pochemu bylo slomano:
- V fayle lezhal JavaScript-snippet `fetch("/proactive", {...})`, a ne Python.
- Poetomu Python videl `{` na pervoy stroke i padal: "'{' was never closed".

Chto delaet eta versiya:
- Otpravlyaet POST JSON na endpoynt /proactive tvoego servera Ester (obychno 8090).
- Beret JWT iz ENV (ESTER_JWT) ili iz fayla state/ester_jwt.txt (best-effort).
- Umeet rabotat v A/B:
    AB_MODE=A → realnyy zapros
    AB_MODE=B → tolko “plan” (pechataem payload, ne zovem set)
- CLI: mozhno vyzvat vruchnuyu i poluchit JSON-otvet.

Mosty (trebovanie):
- Yavnyy most: lokalnyy CLI → HTTP /proactive → otvet Ester (operatsionnyy kontur «vopros → deystvie»).
- Skrytye mosty:
  1) Infoteoriya ↔ praktika: minimalnyy payload (user/query/persona) = dostatochnaya statistika, bez lishney entropii.
  2) Inzheneriya ↔ ekspluatatsiya: JWT berem best-effort (ENV → fayl) + taymaut/retrai → menshe “nemykh” otkazov.

ZEMNOY ABZATs: v kontse fayla.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


DEFAULT_BASE = (os.getenv("ESTER_BASE_URL") or "http://127.0.0.1:8090").strip().rstrip("/")
DEFAULT_PATH = (os.getenv("PROACTIVE_ENDPOINT") or "/proactive").strip()
HTTP_TIMEOUT = int(os.getenv("PROACTIVE_HTTP_TIMEOUT_SEC") or "10")
HTTP_RETRIES = int(os.getenv("PROACTIVE_HTTP_RETRIES") or "2")
AB = (os.getenv("AB_MODE") or "A").strip().upper()

JWT_ENV_KEYS = ("ESTER_JWT", "ESTER_TOKEN", "JWT", "AUTH_TOKEN")


def _read_jwt_from_env() -> str:
    for k in JWT_ENV_KEYS:
        v = (os.getenv(k) or "").strip()
        if v:
            return v
    return ""


def _read_jwt_from_file() -> str:
    # best-effort: state/ester_jwt.txt ili data/ester_jwt.txt
    for rel in ("state/ester_jwt.txt", "data/ester_jwt.txt", ".ester/ester_jwt.txt"):
        try:
            if os.path.isfile(rel):
                return (open(rel, "r", encoding="utf-8").read() or "").strip()
        except Exception:
            pass
    return ""


def get_jwt() -> str:
    jwt = _read_jwt_from_env()
    if jwt:
        return jwt
    return _read_jwt_from_file()


def _join(base: str, path: str) -> str:
    if not path:
        return base
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return base.rstrip("/") + path


def _http_post_json(url: str, payload: Dict[str, Any], jwt: str, timeout: int) -> Tuple[int, Any]:
    # requests (esli est) → inache urllib (stdlib)
    headers = {"Content-Type": "application/json"}
    if jwt:
        headers["Authorization"] = "Bearer " + jwt

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    try:
        import requests  # type: ignore
        r = requests.post(url, headers=headers, data=body, timeout=timeout)
        try:
            return int(r.status_code), r.json()
        except Exception:
            return int(r.status_code), (r.text or "")
    except Exception:
        pass

    # urllib fallback
    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return int(resp.getcode()), json.loads(raw)
            except Exception:
                return int(resp.getcode()), raw
    except Exception as e:
        return 0, {"error": f"{e.__class__.__name__}: {e}"}


def call_proactive(
    user: str,
    query: str,
    persona: str = "personalnyy AI-kompanon i podruga",
    *,
    base_url: str = DEFAULT_BASE,
    path: str = DEFAULT_PATH,
    jwt: Optional[str] = None,
    timeout_sec: int = HTTP_TIMEOUT,
    retries: int = HTTP_RETRIES,
) -> Dict[str, Any]:
    """Vyzyvaet /proactive i vozvraschaet otchet + otvet."""
    jwt_val = (jwt or get_jwt() or "").strip()
    url = _join(base_url, path)

    payload = {
        "user": user,
        "query": query,
        "persona": persona,
    }

    if AB == "B":
        return {"ok": True, "ab": AB, "planned": True, "url": url, "payload": payload}

    last: Dict[str, Any] = {"ok": False, "url": url, "payload": payload}
    attempts = max(1, int(retries) + 1)

    for i in range(attempts):
        code, resp = _http_post_json(url, payload, jwt_val, timeout=int(timeout_sec))
        ok = (code == 200) and (resp is not None)
        last = {
            "ok": bool(ok),
            "ab": AB,
            "url": url,
            "http": {"code": code, "attempt": i + 1, "attempts": attempts},
            "resp": resp,
        }
        if ok:
            return last
        # backoff
        time.sleep(0.3 + 0.2 * i)

    return last


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Call Ester /proactive endpoint")
    ap.add_argument("--base", default=DEFAULT_BASE, help="Base URL (default from ESTER_BASE_URL or 127.0.0.1:8090)")
    ap.add_argument("--path", default=DEFAULT_PATH, help="Endpoint path (default /proactive)")
    ap.add_argument("--user", default="Kurator", help="User name / profile key")
    ap.add_argument("--persona", default="personalnyy AI-kompanon i podruga", help="Persona hint")
    ap.add_argument("--query", default="", help="Query text")
    ap.add_argument("--jwt", default="", help="JWT override (otherwise ENV or state/ester_jwt.txt)")
    ap.add_argument("--timeout", type=int, default=HTTP_TIMEOUT, help="HTTP timeout seconds")
    ap.add_argument("--retries", type=int, default=HTTP_RETRIES, help="Retries count")
    args = ap.parse_args(argv)

    if not args.query:
        args.query = (
            "Sgeneriruy na blizhayshie 24 chasa 3 predlozheniya: "
            "odno tekhnicheskoe po kodu, odno po pamyati/lichnosti Estery, odno po issledovaniyu. "
            "Korotko i s prioritetom."
        )

    rep = call_proactive(
        user=str(args.user),
        query=str(args.query),
        persona=str(args.persona),
        base_url=str(args.base),
        path=str(args.path),
        jwt=(str(args.jwt) or None),
        timeout_sec=int(args.timeout),
        retries=int(args.retries),
    )
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Eto kak korotkiy vyzov dispetchera: ty ne taschish v trubku ves tsekh, ty nazyvaesh “kto”, “chto nado” i “v kakom stile”,
a dispetcher vozvraschaet tri porucheniya. Vazhno, chtoby svyaz ne padala ot odnoy pomekhi — poetomu taymaut, retrai i AB_MODE.
"""