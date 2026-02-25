# -*- coding: utf-8 -*-
"""tools/show_experience_profile_http.py

Utilita dlya prosmotra profilya opyta Ester cherez HTTP-endpoint
/memory/experience/profile.

Features:
- Nikakikh zavisimostey krome standartnoy biblioteki.
- BASE_URL beretsya iz peremennoy okruzheniya or ukazannoy vruchnuyu.
- Safe obrabatyvaet setevye/HTTP-oshibki.
- Format vyvoda druzhelyuben dlya ruchnoy diagnostiki i CI."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def get_base_url() -> str:
    # Prioritet: ENV BASE_URL, zatem defoltnyy lokalnyy server.
    base = os.getenv("BASE_URL") or "http://127.0.0.1:8080"
    return base.rstrip("/")


def fetch_profile(base_url: str) -> Dict[str, Any]:
    url = f"{base_url}/memory/experience/profile"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {
                    "ok": False,
                    "error": "invalid_json",
                    "raw": data[:4000],
                }
    except error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return {
            "ok": False,
            "error": "http_error",
            "status": e.code,
            "body": body[:4000],
        }
    except error.URLError as e:
        return {
            "ok": False,
            "error": "url_error",
            "reason": getattr(e, "reason", str(e)),
        }
    except Exception as e:  # pragma: no cover - zaschitnyy sloy
        return {"ok": False, "error": "unexpected_error", "detail": str(e)}


def print_human(profile_resp: Dict[str, Any]) -> None:
    ok = profile_resp.get("ok", False)
    profile = profile_resp.get("profile") or {}

    print(json.dumps(profile_resp, ensure_ascii=False, indent=2))

    # A brief summary below ZhSION - it’s easy to look at with your eyes.
    print("\n--- summary ---")

    if not ok:
        err = profile_resp.get("error") or profile.get("error")
        if err == "experience_profile_not_implemented":
            print("The experience profile is not yet implemented in the backend."
                  "The alias works, but the experiment module does not provide data.")
        elif err == "no_insights":
            print("There is a profile, but no insights yet: you need at least one successful night cycle.")
        elif err:
            print(f"Experience Profile Error: ZZF0Z")
        else:
            print("ok == False, no error details.")
    else:
        total = profile.get("total_insights")
        top_terms = profile.get("top_terms") or []
        print(f"Profile opyta aktiven. Insaytov: {total}.")
        if top_terms:
            head = ", ".join(map(str, top_terms[:10]))
            print(f"Key terms: ZZF0Z")


def main() -> int:
    base_url = get_base_url()
    profile_resp = fetch_profile(base_url)

    print(f"[experience] BASE_URL={base_url}")
    print_human(profile_resp)

    return 0 if profile_resp.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())