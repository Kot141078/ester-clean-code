# -*- coding: utf-8 -*-
"""
Telegram adapter (legacy script) with strict net_guard checks.
"""
from __future__ import annotations

import json
import os
import threading
import time
import traceback
from typing import Any, Dict, Optional, Tuple

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from modules.net_guard import allow_network, deny_payload


API_URL = os.getenv("ESTER_CHAT_API_URL", "http://127.0.0.1:8080/chat/message")
TG_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
INBOX_DIR = os.path.join(os.getcwd(), "data", "ingest", "telegram_inbox")


def _tg_api_url(path: str) -> str:
    return f"https://api.telegram.org/bot{TG_TOKEN}/{path.lstrip('/')}"


def _tg_file_url(remote_path: str) -> str:
    return f"https://api.telegram.org/file/bot{TG_TOKEN}/{remote_path.lstrip('/')}"


def _check_net(url: str) -> Optional[Dict[str, Any]]:
    if allow_network(url):
        return None
    return deny_payload(url, target="telegram_adapter")


def ensure_inbox() -> None:
    os.makedirs(INBOX_DIR, exist_ok=True)


def _http_get(url: str, **kwargs):
    err = _check_net(url)
    if err is not None:
        return None, err
    if requests is None:
        return None, {"ok": False, "error": "requests_not_installed"}
    try:
        return requests.get(url, **kwargs), None
    except Exception as e:
        return None, {"ok": False, "error": "http_get_failed", "detail": str(e)}


def _http_post(url: str, **kwargs):
    err = _check_net(url)
    if err is not None:
        return None, err
    if requests is None:
        return None, {"ok": False, "error": "requests_not_installed"}
    try:
        return requests.post(url, **kwargs), None
    except Exception as e:
        return None, {"ok": False, "error": "http_post_failed", "detail": str(e)}


def download_file(file_id: str, file_name: str) -> Tuple[Optional[str], Optional[str]]:
    get_file_url = _tg_api_url(f"getFile?file_id={file_id}")
    r, err = _http_get(get_file_url, timeout=20)
    if err is not None:
        return None, f"network_denied_or_failed: {err}"
    if r is None or not r.ok:
        return None, f"getFile error: {getattr(r, 'status_code', 'n/a')}"

    try:
        remote_path = (r.json() or {}).get("result", {}).get("file_path")
    except Exception as e:
        return None, f"getFile invalid json: {e}"
    if not remote_path:
        return None, "no file_path received"

    dl_url = _tg_file_url(str(remote_path))
    net_err = _check_net(dl_url)
    if net_err is not None:
        return None, f"network_denied_or_failed: {net_err}"

    ensure_inbox()
    ts_prefix = str(int(time.time()))
    safe_name = os.path.basename(str(file_name or "unknown_file")).replace(" ", "_")
    local_path = os.path.join(INBOX_DIR, f"{ts_prefix}_{safe_name}")

    try:
        assert requests is not None
        with requests.get(dl_url, stream=True, timeout=60) as r_dl:
            r_dl.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r_dl.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        return None, str(e)

    return local_path, None


def _send_tg_text(chat_id: Any, text: str, parse_mode: Optional[str] = None) -> None:
    url = _tg_api_url("sendMessage")
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    _http_post(url, json=payload, timeout=30)


def _process_text(chat_id: Any, text: str) -> str:
    payload = {
        "message": text,
        "sid": str(chat_id),
        "mode": "judge",
        "author": "TelegramUser",
    }
    r, err = _http_post(API_URL, json=payload, timeout=21600)
    if err is not None:
        return f"Network blocked or API unavailable: {err}"
    if r is None or r.status_code != 200:
        return f"API error: {getattr(r, 'status_code', 'n/a')}"
    try:
        rj = r.json() or {}
    except Exception as e:
        return f"API invalid JSON: {e}"
    reply_text = str(rj.get("reply") or rj.get("answer") or rj.get("text") or "...")
    prov = rj.get("provider")
    if prov:
        reply_text += f"\n\n(Provider: {prov})"
    return reply_text


def listen() -> Dict[str, Any]:
    if not TG_TOKEN:
        msg = "No TELEGRAM_BOT_TOKEN in environment"
        print(f"[TG] {msg}")
        return {"ok": False, "error": msg}

    updates_url = _tg_api_url("getUpdates")
    denied = _check_net(updates_url)
    if denied is not None:
        print(f"[TG] network denied: {denied}")
        return denied

    if requests is None:
        msg = "requests module is not installed"
        print(f"[TG] {msg}")
        return {"ok": False, "error": msg}

    offset = 0
    print(f"[TG] Listening... telegram token configured: {'yes' if bool(TG_TOKEN) else 'no'}")
    print(f"[TG] Inbox: {INBOX_DIR}")

    while True:
        try:
            url = _tg_api_url(f"getUpdates?offset={offset}&timeout=30")
            r, err = _http_get(url, timeout=40)
            if err is not None or r is None:
                print(f"[TG] getUpdates failed: {err}")
                time.sleep(5)
                continue

            try:
                data = r.json() or {}
            except Exception as e:
                print(f"[TG] getUpdates invalid JSON: {e}")
                time.sleep(2)
                continue

            if not data.get("ok"):
                time.sleep(5)
                continue

            for result in data.get("result", []):
                offset = int(result.get("update_id", offset)) + 1
                msg = result.get("message", {}) or {}
                chat_id = (msg.get("chat") or {}).get("id")
                if not chat_id:
                    continue

                doc = msg.get("document")
                photo = msg.get("photo")
                file_target = None
                file_name_display = "file"

                if isinstance(doc, dict):
                    file_target = doc.get("file_id")
                    file_name_display = doc.get("file_name") or "document.bin"
                elif isinstance(photo, list) and photo:
                    file_target = photo[-1].get("file_id")
                    file_name_display = "photo_image.jpg"

                if file_target:
                    _send_tg_text(chat_id, f"Receiving: {file_name_display}...")
                    local_path, dl_err = download_file(str(file_target), str(file_name_display))
                    if dl_err:
                        _send_tg_text(chat_id, f"Download failed: {dl_err}")
                        continue

                    try:
                        from modules.perception.pipeline import ingest_file

                        meta = {
                            "source": "telegram",
                            "chat_id": chat_id,
                            "author": (msg.get("from") or {}).get("username") or "TelegramUser",
                        }
                        reply_text = str(ingest_file(str(local_path), meta))
                    except ImportError:
                        reply_text = f"Saved to inbox: {local_path}. Perception pipeline not installed."
                    except Exception as e_pipe:
                        reply_text = f"Perception error: {e_pipe}"
                        traceback.print_exc()

                    _send_tg_text(chat_id, reply_text)
                    continue

                text = str(msg.get("text") or "")
                if not text:
                    continue
                reply_text = _process_text(chat_id, text)
                _send_tg_text(chat_id, reply_text)

        except Exception as e:
            print(f"[TG] loop error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    listen()
else:
    t = threading.Thread(target=listen, daemon=True)
    t.start()
