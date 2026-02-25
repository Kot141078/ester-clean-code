"""Kompleksnaya proverka Ester-thinking layer.

Zapusk:
  python -m scripts.ester_thinking_suite
  python -m scripts.ester_thinking_suite http # dobavit HTTP-proverku /ester/thinking/quality_once

Skript ne menyaet sostoyanie sistemy:
- chitaem manifest cherez modules.ester.thinking_manifest
- zapuskaem lokalnyy kaskad cherez cascade_closed
- schitaem kachestvo cherez thinking_quality.analyze_cascade
- optsionalno (rezhim http) dergaem uzhe suschestvuyuschiy /ester/thinking/quality_once"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _pp(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def run_local_probe() -> Dict[str, Any]:
    from modules.thinking import cascade_closed
    from modules.ester import thinking_quality

    goal = "quality self-check: human_like probe (suite/local)"
    cascade = cascade_closed.run_cascade(goal)
    quality = thinking_quality.analyze_cascade(cascade)

    return {
        "mode": "local",
        "goal": goal,
        "cascade_ok": bool(cascade.get("ok", True)),
        "cascade_summary": cascade.get("summary"),
        "quality": quality,
    }


def run_manifest_probe() -> Dict[str, Any]:
    from modules.ester import thinking_manifest

    manifest = thinking_manifest.get_manifest()
    described = thinking_manifest.describe_manifest(manifest)

    return {
        "ok": bool(described.get("ok", True)),
        "manifest": described,
    }


def run_http_quality_probe() -> Dict[str, Any]:
    """Sample of the already raised HTTP layer via /ester/thinking/kalita_once.

    We use only the standard library, without third-party dependencies."""
    import urllib.request
    import urllib.error

    url = "http://127.0.0.1:8080/ester/thinking/quality_once"
    payload = {
        "goal": "quality http human_like probe (suite/http)",
        "priority": "high",
        "trace": True,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                j = json.loads(body)
            except json.JSONDecodeError:
                return {
                    "ok": False,
                    "error": "invalid_json",
                    "raw": body[:4000],
                }
    except urllib.error.URLError as e:
        return {
            "ok": False,
            "error": "http_error",
            "details": str(e),
        }

    used = j.get("used") or []
    return {
        "ok": bool(j.get("ok", False)),
        "goal": j.get("goal"),
        "used": used,
        "summary": j.get("summary"),
        "has_quality": "thinking_quality.analyze_cascade" in used,
    }


def main() -> None:
    do_http = len(sys.argv) > 1 and sys.argv[1].lower() == "http"

    print("[ester_thinking_suite] manifest probe:")
    manifest_res = run_manifest_probe()
    print(_pp(manifest_res), "\n")

    print("[ester_thinking_suite] local cascade+quality probe:")
    local_res = run_local_probe()
    print(_pp(local_res), "\n")

    if do_http:
        print("[ester_thinking_suite] http /ester/thinking/quality_once probe:")
        http_res = run_http_quality_probe()
        print(_pp(http_res), "\n")


if __name__ == "__main__":
    main()