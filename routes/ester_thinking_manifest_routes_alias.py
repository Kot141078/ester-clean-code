# -*- coding: utf-8 -*-
"""
routes/ester_thinking_manifest_routes_alias.py

Ester thinking manifest/check HTTP alias.

Marshruty:
- GET /ester/thinking/manifest  — podrobnyy manifest myslitelnykh moduley
- GET /ester/thinking/check     — korotkiy summary (chitaemo cheloveku/skriptam)

Mosty:
- (scripts.ester_thinking_check <-> HTTP) — odni i te zhe funktsii, bez dublirovaniya logiki.
- (modules.ester.thinking_manifest <-> app.py) — akkuratnoe vklyuchenie cherez alias bez pravok yadra.

Zemnoy abzats:
Inzheneru nuzhno bystro ponyat, «vklyuchena li chelovecheskaya golova» u Ester:
chto s kaskadom, voley, treysom, fonom. Etot alias daet JSON c temi zhe
dannymi, chto CLI-skript, chtoby monitoring i paneli ne lezli v internals.
"""

from __future__ import annotations

import os
from typing import Optional

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _ab_enabled() -> bool:
    """Proverka flaga AB dlya HTTP-manifesta.

    Marshruty schitayutsya vklyuchennymi, esli ESTER_THINK_CHECK_AB v:
    - "B", "AB", "ON", "1"
    """
    flag = (os.getenv("ESTER_THINK_CHECK_AB") or "").strip().upper()
    return flag in {"B", "AB", "ON", "1"}


def _load_manifest_module():
    try:
        from modules.ester import thinking_manifest  # type: ignore
    except Exception:
        return None
    return thinking_manifest


def create_blueprint() -> Optional[Blueprint]:
    """Sozdat Blueprint dlya /ester/thinking/manifest i /ester/thinking/check.

    Vozvraschaet None, esli:
    - eksperiment ne vklyuchen;
    - modul thinking_manifest nedostupen.

    Eto sdelano, chtoby alias ne lomal bazovyy app.py.
    """
    if not _ab_enabled():
        return None

    mod = _load_manifest_module()
    if mod is None:
        # Paneli zavisyat ot etogo, no ne kritichnyy funktsional — tikho vykhodim.
        return None

    bp = Blueprint("ester_thinking_manifest", __name__)

    @bp.get("/ester/thinking/manifest")
    def ester_thinking_manifest():
        """Polnyy JSON-manifest myslitelnykh moduley i pokrytiya."""
        manifest = mod.get_manifest()
        return jsonify(manifest)

    @bp.get("/ester/thinking/check")
    def ester_thinking_check():
        """Korotkiy chelovekochitaemyy summary sostoyaniya myshleniya.

        Format otveta:
        {
          "ok": bool,
          "manifest": { ... kak /ester/thinking/manifest ... },
          "summary": "... tekst iz describe_manifest ..." | null
        }
        """
        manifest = mod.get_manifest()
        try:
            summary = mod.describe_manifest(manifest)
        except Exception:
            summary = None

        return jsonify(
            {
                "ok": bool(manifest.get("ok", True)),
                "manifest": manifest,
                "summary": summary,
            }
        )

    return bp


def register(app) -> None:
    """Registratsiya blueprint v Flask-prilozhenii.

    - Nikakikh pobochnykh effektov, esli eksperiment vyklyuchen.
    - Ne pere-registriruem blueprint, esli on uzhe est.
    """
    bp = create_blueprint()
    if bp is None:
        return

    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return

    app.register_blueprint(bp)
    try:
        print("[ester-thinking-manifest/routes] registered /ester/thinking/manifest,/ester/thinking/check")
    except Exception:
        # Log ne kritichen
        pass