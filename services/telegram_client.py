# -*- coding: utf-8 -*-
# services/telegram_client.py
"""TelegramClient - tonkaya obertka nad Bot API.

Podderzhano (ispolzuetsya v UI/routakh):
  • send_message, get_updates, set_webhook, delete_webhook
  • get_me, get_file
  • set_my_name, set_my_short_description, set_my_description
  • get_my_commands, set_my_commands

Zemnoy abzats (inzheneriya):
Ediny klient umenshaet raskhozhdenie vyzovov: odin HTTP-stek, edinye taymauty i obrabotka oshibok.
Metody mappyat 1:1 na Bot API i legko proslezhivayutsya v logakh.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): odin “sensor/effektornyy” kanal k Telegram uproschaet obratnuyu svyaz.
- Skrytyy 1 (Infoteoriya ↔ Interfeysy): unifikatsiya API-stsenariev snizhaet entropiyu integratsii mezhdu UI i bekom.
- Skrytyy 2 (Anatomiya ↔ PO): kak edinyy nervnyy puchok - raznye signaly, odna provodyaschaya sistema.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class TelegramClient:
    def __init__(self, bot_token: Optional[str] = None, timeout: int = 10):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
        self.base = f"https://api.telegram.org/bot{self.bot_token}"
        self.timeout = timeout

    # ----- low-level -----
    def _post(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}/{method}"
        resp = requests.post(url, json=data, timeout=self.timeout)
        resp.raise_for_status()
        js = resp.json()
        if not js.get("ok"):
            raise RuntimeError(f"Telegram API error for {method}: {js}")
        return js

    def _get(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}/{method}"
        resp = requests.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        js = resp.json()
        if not js.get("ok"):
            raise RuntimeError(f"Telegram API error for {method}: {js}")
        return js

    # ----- core methods -----
    def send_message(self, chat_id: int | str, text: str, parse_mode: Optional[str] = None) -> Dict[str, Any]:
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._post("sendMessage", payload)

    def set_webhook(
        self,
        url: str,
        secret_token: Optional[str] = None,
        allowed_updates: Optional[list[str]] = None,
        drop_pending_updates: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "url": url,
            "drop_pending_updates": drop_pending_updates,
        }
        if secret_token:
            payload["secret_token"] = secret_token
        if allowed_updates:
            payload["allowed_updates"] = allowed_updates
        return self._post("setWebhook", payload)

    def delete_webhook(self, drop_pending_updates: bool = True) -> Dict[str, Any]:
        return self._post("deleteWebhook", {"drop_pending_updates": drop_pending_updates})

    def get_updates(self, offset: Optional[int] = None, limit: int = 50, timeout: int = 10) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        return self._get("getUpdates", payload)

    # ----- extras used by control UI / webhook -----
    def get_me(self) -> Dict[str, Any]:
        return self._get("getMe", {})

    def get_file(self, file_id: str) -> Dict[str, Any]:
        return self._get("getFile", {"file_id": file_id})

    def set_my_name(self, name: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": name}
        if language_code:
            payload["language_code"] = language_code
        return self._post("setMyName", payload)

    def set_my_short_description(self, short_description: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"short_description": short_description}
        if language_code:
            payload["language_code"] = language_code
        return self._post("setMyShortDescription", payload)

    def set_my_description(self, description: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"description": description}
        if language_code:
            payload["language_code"] = language_code
        return self._post("setMyDescription", payload)

    def get_my_commands(self, scope: Optional[Dict[str, Any]] = None, language_code: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if scope:
            payload["scope"] = scope
        if language_code:
            payload["language_code"] = language_code
        return self._get("getMyCommands", payload)

    def set_my_commands(
        self,
        commands: list[dict],
        scope: Optional[Dict[str, Any]] = None,
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"commands": commands}
        if scope:
            payload["scope"] = scope
        if language_code:
            payload["language_code"] = language_code
# return self._post("setMyCommands", payload)