# -*- coding: utf-8 -*-
"""
routes/ui_portal.py - Glavnyy portal i chat (avto-JWT dlya Papa).

MOSTY:
- (Yavnyy) Na GET /portal, esli tokena net - prostavlyaet kuku cherez auto_jwt.
- (Skrytyy #1) Ostalnoy funktsional bez izmeneniy: /ui/chat/*, /ui/mode i t.d.
- (Skrytyy #2) Sobytiya UI ostayutsya v events_bus, chtoby lyubye slushateli mogli reagirovat.

ZEMNOY ABZATs:
«Podnesli propusk k turniketu» - i srazu proshli: token kladetsya sam, dialog nachinaetsya mgnovenno.

# c=a+b
"""
from __future__ import annotations
import os, time, json, base64
from typing import Any, Dict, List
from flask import Blueprint, render_template, request, jsonify, make_response, redirect, url_for
from modules.auth.auto_jwt import ensure_papa_cookie
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ui_portal", __name__)

def register(app):
    app.register_blueprint(bp)

DATA_DIR = os.path.join("data", "ui")
os.makedirs(DATA_DIR, exist_ok=True)
CHAT_FILE = os.path.join(DATA_DIR, "chat.jsonl")
MODE_FILE = os.path.join("data", "runtime", "mode.txt")

def _append_line(obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CHAT_FILE), exist_ok=True)
    with open(CHAT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _read_lines(since_ts: float = 0.0, limit: int = 200) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not os.path.isfile(CHAT_FILE):
        return items
    with open(CHAT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if float(obj.get("ts", 0.0)) >= since_ts:
                    items.append(obj)
            except Exception:
                continue
    items.sort(key=lambda x: x.get("ts", 0))
    if len(items) > limit:
        items = items[-limit:]
    return items

def _emit(kind: str, payload: Dict[str, Any]) -> None:
    try:
        from modules import events_bus
        events_bus.publish(kind, payload)
    except Exception:
        pass

def _mode_set(m: str) -> None:
    os.makedirs(os.path.dirname(MODE_FILE), exist_ok=True)
    with open(MODE_FILE, "w", encoding="utf-8") as f:
        f.write(m.strip())

def _mode_get() -> str:
    if os.path.isfile(MODE_FILE):
        try:
            return (open(MODE_FILE, "r", encoding="utf-8").read() or "local").strip()
        except Exception:
            pass
    return os.getenv("AUTHORING_LLM_BACKEND", "local")

@bp.get("/portal")
def portal():
    try:
        target = url_for("admin_index.admin_portal_page")
    except Exception:
        target = "/admin/portal"
    resp = make_response(redirect(target, code=302))
    ensure_papa_cookie(resp)
    return resp

@bp.get("/ui/modes")
def modes_get():
    return jsonify({"ok": True, "mode": _mode_get(), "available": ["judge", "local", "cloud"]})

@bp.post("/ui/mode")
def modes_set():
    data = request.get_json(force=True, silent=True) or {}
    m = str(data.get("mode", "")).strip().lower()
    if m not in ("judge", "local", "cloud"):
        return jsonify({"ok": False, "error": "bad mode"}), 400
    _mode_set(m)
    _emit("ui.mode.changed", {"mode": m})
    return jsonify({"ok": True, "mode": m})

@bp.post("/ui/chat/send")
def chat_send():
    data = request.get_json(force=True, silent=True) or {}
    text = str(data.get("text", "") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400

    now = time.time()
    user = os.getenv("ESTER_DEFAULT_USER", "Owner")
    msg_user = {"id": f"m-{int(now*1000)}-u", "ts": now, "role": "user", "user": user, "text": text}
    _append_line(msg_user)
    _emit("ui.chat.user", {"user": user, "text": text})

    reply_text = None
    try:
        from modules.thinking.loop_full import answer_sync  # type: ignore
        reply_text = answer_sync(text, mode=_mode_get())
    except Exception:
        pass
    if not reply_text:
        reply_text = f"({ _mode_get() }) Ya uslyshala: {text}"

    now2 = time.time()
    msg_ai = {"id": f"m-{int(now2*1000)}-a", "ts": now2, "role": "assistant", "user": "Ester", "text": reply_text}
    _append_line(msg_ai)
    _emit("ui.chat.assistant", {"text": reply_text})
    return jsonify({"ok": True, "messages": [msg_user, msg_ai]})

@bp.get("/ui/chat/feed")
def chat_feed():
    since = float(request.args.get("since", "0") or "0")
    limit = int(request.args.get("limit", "200") or "200")
    return jsonify({"ok": True, "items": _read_lines(since_ts=since, limit=limit)})

@bp.post("/ui/chat/upload")
def chat_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "file required"}), 400
    f = request.files["file"]
    b = f.read()
    ok = False
    try:
        import ingestion  # type: ignore
        ingestion.ingest_bytes(b, filename=f.filename or "upload.bin", source="ui.upload")
        ok = True
    except Exception:
        try:
            from memory_manager import write  # type: ignore
            write(f"upload:{f.filename}", b.decode("utf-8", errors="ignore"))
            ok = True
        except Exception:
            pass
    ts = time.time()
    note = f"Fayl {f.filename} zagruzhen ({len(b)} bayt)" if ok else f"Ne udalos obrabotat {f.filename}"
    _append_line({"id": f"m-{int(ts*1000)}-sys", "ts": ts, "role": "system", "user": "Ester", "text": note})
    return jsonify({"ok": ok, "note": note})
# c=a+b
