# -*- coding: utf-8 -*-
"""routes/ester_thinking_manifest_routes_alias.py

Ester thinking manifest/check HTTP alias.

Route:
- GET /ester/thinking/manifest — podrobnyy manifest myslitelnykh moduley
- GET /ester/thinking/check - short summary (chitaemo cheloveku/skriptam)

Mosty:
- (scripts.ester_thinking_check <-> HTTP) - odni i te zhe funktsii, bez dublirovaniya logiciki.
- (modules.ester.thinking_manifest <-> app.py) - akkuratnoe vklyuchenie cherez alias bez pravok yadra.

Zemnoy abzats:
Inzheneru nuzhno bystro ponyat, “vklyuchena li chelovecheskaya golova” u Ester:
what s kaskadom, voley, treysom, fonom. This alias daet JSON with temi zhe
dannymi, what CLI-skript, what monitoring i paneli ne lezli v internals."""

from __future__ import annotations

import os
from typing import Optional

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _ab_enabled() -> bool:
    """Checking the AB flag for the HTTP manifest.

    Routes are considered enabled if ESTER_THINK_CHECK_AB is in:
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

    Vozvraschaet None, if:
    - experiment ne vklyuchen;
    - module thinking_manifest unavailable.

    This is done, chtoby alias ne lomal bazovyy app.py."""
    if not _ab_enabled():
        return None

    mod = _load_manifest_module()
    if mod is None:
        # The panels depend on this, but the non-critical functionality is silent.
        return None

    bp = Blueprint("ester_thinking_manifest", __name__)

    @bp.get("/ester/thinking/manifest")
    def ester_thinking_manifest():
        """Complete ZhSON-manifest of thought modules and coverage."""
        manifest = mod.get_manifest()
        return jsonify(manifest)

    @bp.get("/ester/thinking/check")
    def ester_thinking_check():
        """Korotkiy chelovekochitaemyy summary sostoyaniya myshleniya.

        Format answer:
        {
          "ok": bool,
          "manifest": { ... kak /ester/thinking/manifest ... },
          "summary": "... text iz describe_manifest ..." | null
        }"""
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
    """Registration blueprint v Flask-prilozhenii.

    - Nikakikh pobochnykh effektov, esli eksperiment vyklyuchen.
    - Ne pere-registriruem blueprint, esli on uzhe est."""
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
