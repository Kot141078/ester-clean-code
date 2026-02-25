# -*- coding: utf-8 -*-
"""app - zaschischennyy karkas zapuska Ester.

Iteratsiya U1 + U2:
- U1: Unicode-safe razbor tel POST (UTF-8/UTF-16/CP1251/BOM).
- U2: “Remont” mojibake na vykhode iz /mem_boot/qa i /chat_boot/history
      (i echo iz /mem_boot/remember), bez vtorzheniya v modules.memory.

MOSTY:
- Yavnyy: Set ↔ Memory - remontiruem vyvod, sokhranyaya API kontrakty.
- Skrytyy #1: Inzheneriya OS ↔ Lingvistika — evristika detekta mojibake.
- Skrytyy #2: UX ↔ Nadezhnost — dazhe starye korrapt-zapisi chitayutsya “po-lyudski”.

ZEMNOY ABZATs:
Esli gluboko v pamyati fayly otkryvayutsya ne v UTF-8, poyavlyayutsya “Ð…Ñ...”.
My ne perepilivaem vsyu pamyat seychas — myagko lechim vyvod: esli stroka
vyglyadit kak mojibake, perekodiruem ee v realnuyu kirillitsu.

# c=a+b"""
from __future__ import annotations
import os
import json
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from flask import Flask, jsonify, current_app, Response
from werkzeug.wrappers import Request

# Sovmestimost i rannie aliasy
import compat  # noqa: F401
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_DIR = Path(os.getcwd()) / "data"
(DATA_DIR / "rate_limit").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "memory").mkdir(parents=True, exist_ok=True)

def _bringup_log(msg: str) -> None:
    try:
        with open(DATA_DIR / "bringup.log", "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass

def _safe_json_dumps(obj: Any) -> str:
    class _Encoder(json.JSONEncoder):
        def default(self, o):  # noqa: N802
            try:
                return str(o)
            except Exception:
                try:
                    return repr(o)
                except Exception:
                    return "<unserializable>"
    return json.dumps(obj, ensure_ascii=False, cls=_Encoder, separators=(",", ":"))

# ---------- bezopasnyy razbor JSON tela (U1) ----------
def _detect_charset_from_ct(ct: Optional[str]) -> Optional[str]:
    if not ct:
        return None
    ct_low = ct.lower()
    if "charset=" in ct_low:
        try:
            return ct_low.split("charset=", 1)[1].split(";")[0].strip().strip('"').strip("'")
        except Exception:
            return None
    return None

def _decode_bytes_safely(b: bytes, hint: Optional[str]) -> str:
    if not isinstance(b, (bytes, bytearray)):
        return str(b)
    if hint:
        try:
            return b.decode(hint, errors="strict")
        except Exception:
            pass
    try:
        if b.startswith(b"\xef\xbb\xbf"):
            return b[3:].decode("utf-8", errors="strict")
        if b.startswith(b"\xff\xfe"):
            return b[2:].decode("utf-16-le", errors="strict")
        if b.startswith(b"\xfe\xff"):
            return b[2:].decode("utf-16-be", errors="strict")
    except Exception:
        pass
    for enc in ("utf-8", "utf-16-le", "cp1251", "latin-1"):
        try:
            return b.decode(enc, errors="strict")
        except Exception:
            continue
    return ""

def _parse_json_body_safely(environ) -> Dict[str, Any]:
    try:
        req = Request(environ)
        raw = req.get_data(cache=False)  # bytes
        ct = req.content_type or ""
        hint = _detect_charset_from_ct(ct)
        text = _decode_bytes_safely(raw, hint)
        if not text or not text.strip():
            return {}
        return json.loads(text)
    except Exception as e:
        _bringup_log(f"_parse_json_body_safely failed: {repr(e)}")
        _bringup_log(traceback.format_exc())
        return {}

# ---------- U2: remont mojibake ----------
def _looks_mojibake(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    # evristika: dolya “Ð Ñ �” simvolov i otsutstvie kirillitsy
    bad_chars = sum(1 for ch in s if ch in "ÐÑ�")
    cyr = sum(1 for ch in s if "a" <= ch <= "ya" or "A" <= ch <= "Ya" or ch == "E" or ch == "e")
    return bad_chars >= max(3, len(s) // 12) and cyr == 0

def _repair_mojibake_str(s: str) -> str:
    if not isinstance(s, str):
        return s
    if not _looks_mojibake(s):
        return s
    # We treat the most common case: UTF-8 bytes were read as Latin-1
    try:
        return s.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
    except Exception:
        # spare: try through sp1252
        try:
            return s.encode("cp1252", errors="strict").decode("utf-8", errors="strict")
        except Exception:
            return s

def _repair_mojibake(obj: Any) -> Any:
    # Recursively repairing strings in known fields
    if isinstance(obj, str):
        return _repair_mojibake_str(obj)
    if isinstance(obj, list):
        return [_repair_mojibake(x) for x in obj]
    if isinstance(obj, dict):
        fixed = {}
        for k, v in obj.items():
            if k in ("text", "answer", "meta", "role", "tags"):  # key fields
                fixed[k] = _repair_mojibake(v)
            elif k in ("contexts", "items"):  # massivy obektov
                fixed[k] = _repair_mojibake(v)
            else:
                fixed[k] = v
        return fixed
    return obj

# ---------- prilozhenie ----------
def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["ESTER_ROOT"] = str(Path(__file__).resolve().parent)

    # Registration of blueprints (we don’t crash the process if there are errors)
    try:
        from modules.register_all import register_all as _register_all
        _fn = _register_all
        if callable(_fn):
            boot = _fn(app)
            app.config["ESTER_BOOT_INFO"] = boot
        else:
            raise ImportError('register_all not available')
    except Exception as e:
        _bringup_log("register_all failed: " + repr(e))
        _bringup_log(traceback.format_exc())
        app.config["ESTER_BOOT_INFO"] = {
            "registered": [],
            "skipped": {"syntax": [], "import": [], "duplicate_bp": [], "no_entry": []},
            "error": repr(e),
        }

    # Bazovye marshruty
    @app.get("/ping")
    def ping():
        return jsonify(ok=True)

    @app.get("/")
    def root():
        info = app.config.get("ESTER_BOOT_INFO", {})
        payload = {"ok": True, "boot": info}
        return current_app.response_class(_safe_json_dumps(payload), mimetype="application/json")

    # ---------- SAFE handlers ----------
    def _direct_health(environ) -> Response:
        info = app.config.get("ESTER_BOOT_INFO", {})
        reg = info.get("registered", []) if isinstance(info, dict) else []
        skipped = info.get("skipped", {}) if isinstance(info, dict) else {}
        payload = {"ok": True, "registered_count": len(reg), "skipped": skipped}
        return Response(_safe_json_dumps(payload), mimetype="application/json")

    def _direct_root(environ) -> Response:
        info = app.config.get("ESTER_BOOT_INFO", {})
        payload = {"ok": True, "boot": info}
        return Response(_safe_json_dumps(payload), mimetype="application/json")

    def _direct_ui(environ) -> Response:
        info = app.config.get("ESTER_BOOT_INFO", {})
        try:
            pretty = json.dumps(info, ensure_ascii=False, indent=2)
        except Exception:
            pretty = _safe_json_dumps(info)
        body = f"""<html><head><meta charset="utf-8"><title>Ester • Safe Boot</title></head>
<body>
<h1>Ester • Safe Boot</h1>
<pre>{pretty}</pre>
</body></html>"""
        return Response(body, mimetype="text/html")

    # ---- memory (SAFE) ----
    def _direct_mem_remember(environ) -> Response:
        try:
            from modules.memory import remember as mem_remember
            data = _parse_json_body_safely(environ)
            e = mem_remember({
                "text": str(data.get("text", "")),
                "role": str(data.get("role", "user")),
                "tags": list(data.get("tags", [])),
                "meta": dict(data.get("meta", {})),
            })
            # Yu2: repairing the echo event
            return Response(_safe_json_dumps(_repair_mojibake({"ok": True, "event": e})), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_mem_remember failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_mem_qa(environ) -> Response:
        try:
            from modules.memory import qa as mem_qa
            req = Request(environ)
            q = req.args.get("q", "")
            res = mem_qa(q)
            # Yu2: repairing the answer (answer + context*sch.text/…)
            fixed = _repair_mojibake(res)
            return Response(_safe_json_dumps(fixed), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_mem_qa failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_mem_daily(environ) -> Response:
        try:
            from modules.memory import daily_cycle as mem_daily
            res = mem_daily()
            return Response(_safe_json_dumps(res), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_mem_daily failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    # ---- idle (SAFE) ----
    def _direct_idle_start(environ) -> Response:
        try:
            from modules.thinking.idle_engine import idle_start
            res = idle_start()
            return Response(_safe_json_dumps({"ok": True, **res}), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_idle_start failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_idle_stop(environ) -> Response:
        try:
            from modules.thinking.idle_engine import idle_stop
            res = idle_stop()
            return Response(_safe_json_dumps({"ok": True, **res}), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_idle_stop failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_idle_status(environ) -> Response:
        try:
            from modules.thinking.idle_engine import idle_status
            res = idle_status()
            return Response(_safe_json_dumps({"ok": True, **res}), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_idle_status failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_idle_config(environ) -> Response:
        try:
            from modules.thinking.idle_engine import idle_configure
            data = _parse_json_body_safely(environ)
            res = idle_configure({
                "mode": data.get("mode"),
                "gpu_mode": data.get("gpu_mode"),
            })
            return Response(_safe_json_dumps({"ok": True, "config": res}), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_idle_config failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    # ---- chat (SAFE) ----
    def _direct_chat_send(environ) -> Response:
        try:
            from modules.chat import chat_reply
            data = _parse_json_body_safely(environ)
            text = str(data.get("text", ""))
            user = data.get("user")
            res = chat_reply(text, user_name=user)
            return Response(_safe_json_dumps(res), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_chat_send failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_chat_history(environ) -> Response:
        """Latest messages (role in ZZF0Z with tag xat). Repair of Mozhiwake (Yu2)."""
        try:
            try:
                from modules.memory import get_store
            except Exception:
                from modules.memory.api import get_store  # type: ignore
            req = Request(environ)
            try:
                n = int(req.args.get("n", "20"))
            except Exception:
                n = 20
            n = max(1, min(n, 200))
            store = get_store()
            items: List[dict] = store.recent(limit=500)
            chats = [ev for ev in items if "chat" in (ev.get("tags") or [])]
            res = chats[-n:]
            fixed = _repair_mojibake({"ok": True, "items": res})
            return Response(_safe_json_dumps(fixed), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_chat_history failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    # ---- think_boot (SAFE) ----
    def _direct_think_config(environ) -> Response:
        try:
            from modules.thinking import loop_basic as tb
            data = _parse_json_body_safely(environ)
            res = tb.configure(data or {})
            return Response(_safe_json_dumps(res), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_think_config failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_think_start(environ) -> Response:
        try:
            from modules.thinking import loop_basic as tb
            res = tb.start()
            return Response(_safe_json_dumps(res), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_think_start failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_think_stop(environ) -> Response:
        try:
            from modules.thinking import loop_basic as tb
            res = tb.stop()
            return Response(_safe_json_dumps(res), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_think_stop failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_think_status(environ) -> Response:
        try:
            from modules.thinking import loop_basic as tb
            res = tb.status()
            return Response(_safe_json_dumps(res), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_think_status failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    def _direct_think_task(environ) -> Response:
        try:
            from modules.thinking import loop_basic as tb
            data = _parse_json_body_safely(environ)
            payload = data if isinstance(data, dict) else {}
            res = tb.enqueue(payload)
            return Response(_safe_json_dumps(res), mimetype="application/json")
        except Exception as ex:
            _bringup_log("direct_think_task failed: " + repr(ex))
            _bringup_log(traceback.format_exc())
            return Response('{"ok":false}', status=500, mimetype="application/json")

    # ---- well-known (Chrome DevTools) ----
    def _direct_wellknown_devtools(environ) -> Response:
        payload = {
            "ok": True,
            "app": "Ester",
            "purpose": "devtools-probe",
            "note": "compat payload to avoid 500 on /.well-known/appspecific/com.chrome.devtools.json"
        }
        return Response(_safe_json_dumps(payload), mimetype="application/json")

    SAFE_MAP: Dict[str, Callable[[dict], Response]] = {
        "/ping": lambda e: Response('{"ok":true}', mimetype="application/json"),
        "/": _direct_root,
        "/health": _direct_health,
        "/ui": _direct_ui,
        # memory
        "/mem_boot/remember": _direct_mem_remember,
        "/mem_boot/qa": _direct_mem_qa,
        "/mem_boot/daily_cycle": _direct_mem_daily,
        # idle
        "/idle/start": _direct_idle_start,
        "/idle/stop": _direct_idle_stop,
        "/idle/status": _direct_idle_status,
        "/idle/config": _direct_idle_config,
        # chat
        "/chat_boot/send": _direct_chat_send,
        "/chat_boot/history": _direct_chat_history,
        # think_boot
        "/think_boot/config": _direct_think_config,
        "/think_boot/start": _direct_think_start,
        "/think_boot/stop": _direct_think_stop,
        "/think_boot/status": _direct_think_status,
        "/think_boot/task": _direct_think_task,
        # well-known
        "/.well-known/appspecific/com.chrome.devtools.json": _direct_wellknown_devtools,
    }

    base_wsgi = app.wsgi_app

    def guarded_wsgi(environ, start_response):
        try:
            path = environ.get("PATH_INFO") or ""
            if path in SAFE_MAP and os.getenv("ESTER_BYPASS_SAFE", "1") != "0":
                try:
                    resp = SAFE_MAP[path](environ)
                    return resp(environ, start_response)
                except Exception as e:
                    _bringup_log(f"safe handler failed at {path}: {repr(e)}")
                    _bringup_log(traceback.format_exc())
                    err = Response("Safe handler failure", status=500, mimetype="text/plain; charset=utf-8")
                    return err(environ, start_response)
            return base_wsgi(environ, start_response)
        except Exception as e:
            _bringup_log("WSGI guard caught: " + repr(e))
            _bringup_log(traceback.format_exc())
            err = Response("Internal error (guarded). See data/bringup.log", status=500, mimetype="text/plain; charset=utf-8")
            return err(environ, start_response)

    app.wsgi_app = guarded_wsgi  # type: ignore
    return app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "8080"))
    app.run(host=host, port=port, debug=False)
# c=a+b
