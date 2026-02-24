# -*- coding: utf-8 -*-
"""
routes/admin_telegram.py - панель Telegram fallback: настройки, статус, отправка.

Маршруты:
  • GET  /admin/telegram                 - HTML
  • GET  /admin/telegram/status          - токен(маска), чат, курсор, inbox-сводка
  • POST /admin/telegram/config          - {token?, chat_id?}
  • POST /admin/telegram/ping            - тестовый ping→pong
  • POST /admin/telegram/send            - {path, kind, chat_id?} - отправка файла
  • GET  /admin/telegram/inbox           - сводка входящих

Земной абзац:
Это «пульт телеграфа»: прописал токен/чат, проверил связь, отправил файл.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, jsonify, render_template, request

try:
    from modules.telegram.settings import load_settings, save_settings, set_token, set_chat, mask_token  # type: ignore
except Exception:
    load_settings = None  # type: ignore[assignment]
    save_settings = None  # type: ignore[assignment]
    set_token = None  # type: ignore[assignment]
    set_chat = None  # type: ignore[assignment]
    mask_token = None  # type: ignore[assignment]

try:
    from modules.telegram.api import tg_send_message  # type: ignore
except Exception:
    tg_send_message = None  # type: ignore[assignment]

try:
    from modules.telegram.bridge import send_file_chunked, list_inbox, last_ticket_path, last_package_path  # type: ignore
except Exception:
    send_file_chunked = None  # type: ignore[assignment]
    list_inbox = None  # type: ignore[assignment]
    last_ticket_path = None  # type: ignore[assignment]
    last_package_path = None  # type: ignore[assignment]

from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_tg = Blueprint("admin_telegram", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()


def _settings_path() -> Path:
    return Path("data") / "telegram_admin_settings.json"


def _env_token() -> str:
    return str(
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("TELEGRAM_TOKEN")
        or os.getenv("TG_BOT_TOKEN")
        or ""
    ).strip()


def _mask_token_local(tok: Any) -> str:
    s = str(tok or "").strip()
    if not s:
        return ""
    if len(s) <= 12:
        return s[:3] + "..." + s[-2:]
    return s[:6] + "..." + s[-4:]


def _load_settings_local() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {"token": _env_token(), "chats": {}, "cursor": {}}
    p = _settings_path()
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg["token"] = str(raw.get("token") or cfg.get("token") or "")
                chats = raw.get("chats") or {}
                cursor = raw.get("cursor") or {}
                cfg["chats"] = dict(chats) if isinstance(chats, dict) else {}
                cfg["cursor"] = dict(cursor) if isinstance(cursor, dict) else {}
        except Exception:
            pass
    return cfg


def _save_settings_local(cfg: Dict[str, Any]) -> Dict[str, Any]:
    p = _settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "token": str(cfg.get("token") or ""),
        "chats": dict(cfg.get("chats") or {}),
        "cursor": dict(cfg.get("cursor") or {}),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(p)}


def _load_settings_safe() -> Dict[str, Any]:
    if callable(load_settings):
        try:
            got = load_settings()
            if isinstance(got, dict):
                return got
        except Exception:
            pass
    return _load_settings_local()


def _set_token_safe(token: str) -> Dict[str, Any]:
    if callable(set_token):
        try:
            return dict(set_token(token))
        except Exception:
            pass
    cfg = _load_settings_local()
    cfg["token"] = str(token or "").strip()
    _save_settings_local(cfg)
    tok = str(cfg["token"])
    if tok:
        os.environ["TELEGRAM_TOKEN"] = tok
        os.environ["TELEGRAM_BOT_TOKEN"] = tok
        os.environ["TG_BOT_TOKEN"] = tok
    return {"ok": True, "token_mask": _mask_token_local(tok)}


def _set_chat_safe(chat_id: int) -> Dict[str, Any]:
    if callable(set_chat):
        try:
            return dict(set_chat(chat_id))
        except Exception:
            pass
    cfg = _load_settings_local()
    chats = dict(cfg.get("chats") or {})
    chats["last_chat"] = int(chat_id)
    cfg["chats"] = chats
    _save_settings_local(cfg)
    return {"ok": True, "last_chat": int(chat_id)}


def _mask_token_safe(tok: Any) -> str:
    if callable(mask_token):
        try:
            return str(mask_token(tok))
        except Exception:
            pass
    return _mask_token_local(tok)


def _tg_send_message_safe(token: str, chat_id: int, text: str) -> Dict[str, Any]:
    if callable(tg_send_message):
        try:
            rep = tg_send_message(token, chat_id, text)
            return dict(rep) if isinstance(rep, dict) else {"ok": True, "result": rep}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    try:
        import requests

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": int(chat_id), "text": str(text or "")},
            timeout=20,
        )
        data = resp.json() if resp.content else {"ok": False, "error": "empty_response"}
        if not isinstance(data, dict):
            data = {"ok": False, "error": "invalid_response"}
        data.setdefault("status_code", int(resp.status_code))
        return data
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _send_file_chunked_safe(token: str, chat_id: int, path: str, kind: str) -> Dict[str, Any]:
    if callable(send_file_chunked):
        try:
            rep = send_file_chunked(token, chat_id, path, kind=kind)
            return dict(rep) if isinstance(rep, dict) else {"ok": True, "result": rep}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    p = Path(str(path or "").strip())
    if not p.is_file():
        return {"ok": False, "error": "file-not-found", "path": str(p)}
    try:
        import requests

        url = f"https://api.telegram.org/bot{token}/sendDocument"
        with p.open("rb") as f:
            resp = requests.post(
                url,
                data={
                    "chat_id": str(chat_id),
                    "caption": f"{kind or 'file'}: {p.name}",
                },
                files={"document": (p.name, f)},
                timeout=120,
            )
        data = resp.json() if resp.content else {"ok": False, "error": "empty_response"}
        if not isinstance(data, dict):
            data = {"ok": False, "error": "invalid_response"}
        return {
            "ok": bool(data.get("ok")),
            "path": str(p),
            "kind": str(kind or "file"),
            "status_code": int(resp.status_code),
            "api": data,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "path": str(p)}


def _last_ticket_path_safe() -> str | None:
    if callable(last_ticket_path):
        try:
            got = last_ticket_path()
            return str(got) if got else None
        except Exception:
            pass
    return None


def _last_package_path_safe() -> str | None:
    if callable(last_package_path):
        try:
            got = last_package_path()
            return str(got) if got else None
        except Exception:
            pass
    return None


def _list_inbox_safe() -> Dict[str, Any]:
    if callable(list_inbox):
        try:
            got = list_inbox()
            if isinstance(got, dict):
                return got
            return {"ok": True, "items": got}
        except Exception:
            pass

    inbox_dir = Path("data") / "ingest" / "telegram_inbox"
    rows = []
    if inbox_dir.is_dir():
        files = sorted(
            [p for p in inbox_dir.iterdir() if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in files[:50]:
            st = p.stat()
            rows.append(
                {
                    "name": p.name,
                    "path": str(p),
                    "size": int(st.st_size),
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    return {
        "ok": True,
        "count": len(rows),
        "items": rows,
        "last_ticket": _last_ticket_path_safe(),
        "last_package": _last_package_path_safe(),
    }


@bp_tg.get("/admin/telegram")
def page():
    return render_template("admin_telegram.html", ab=AB)


@bp_tg.get("/admin/telegram/status")
def status():
    cfg = _load_settings_safe()
    tok_mask = _mask_token_safe(cfg.get("token"))
    inbox = _list_inbox_safe()
    return jsonify(
        {
            "ok": True,
            "ab": AB,
            "token_mask": tok_mask,
            "chats": cfg.get("chats", {}),
            "cursor": cfg.get("cursor", {}),
            "inbox": inbox,
        }
    )


@bp_tg.post("/admin/telegram/config")
def config():
    body = request.get_json(silent=True) or {}
    tok = (body.get("token") or "").strip()
    chat = body.get("chat_id")
    res: Dict[str, Any] = {}
    if tok:
        res["token"] = _set_token_safe(tok)
    if chat is not None:
        try:
            res["chat"] = _set_chat_safe(int(chat))
        except Exception:
            return jsonify({"ok": False, "error": "chat_id_invalid"}), 400
    return jsonify({"ok": True, "res": res})


@bp_tg.post("/admin/telegram/ping")
def ping():
    cfg = _load_settings_safe()
    tok = str(cfg.get("token") or "").strip()
    chat = (cfg.get("chats") or {}).get("last_chat")
    if not tok or not chat:
        return jsonify({"ok": False, "error": "token-or-chat-missing"}), 400
    res = _tg_send_message_safe(tok, int(chat), "ping")
    code = 200 if bool(res.get("ok")) else 502
    return jsonify({"ok": bool(res.get("ok")), "send": res}), code


@bp_tg.post("/admin/telegram/send")
def send():
    body = request.get_json(silent=True) or {}
    path = (body.get("path") or "").strip()
    kind = (body.get("kind") or "package").strip()
    chat = body.get("chat_id")
    cfg = _load_settings_safe()
    tok = str(cfg.get("token") or "").strip()
    if not tok:
        return jsonify({"ok": False, "error": "no-token"}), 400
    if not chat:
        chat = (cfg.get("chats") or {}).get("last_chat")
    if not chat:
        return jsonify({"ok": False, "error": "no-chat"}), 400
    res = _send_file_chunked_safe(tok, int(chat), path, kind=kind)
    code = 200 if bool(res.get("ok")) else 502
    return jsonify(res), code


@bp_tg.get("/admin/telegram/inbox")
def inbox():
    return jsonify(_list_inbox_safe())


def register_admin_telegram(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_tg)
    if url_prefix:
        from flask import Blueprint as _BP

        pref = _BP("admin_telegram_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/telegram")
        def _p():
            return page()

        @pref.get("/admin/telegram/status")
        def _s():
            return status()

        @pref.post("/admin/telegram/config")
        def _c():
            return config()

        @pref.post("/admin/telegram/ping")
        def _pp():
            return ping()

        @pref.post("/admin/telegram/send")
        def _se():
            return send()

        @pref.get("/admin/telegram/inbox")
        def _i():
            return inbox()

        app.register_blueprint(pref)


def register(app):
    app.register_blueprint(bp_tg)
    return app
