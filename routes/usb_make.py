# -*- coding: utf-8 -*-
"""
routes/usb_make.py — UI/REST: master sozdaniya Re proverki portable-fleshki Ester.

Marshruty:
  • GET  /admin/usb/make           — HTML-stranitsa mastera
  • GET  /admin/usb/drives         — spisok tomov (JSON)
  • POST /admin/usb/make/plan      — vernut plan ukladki (JSON)
  • POST /admin/usb/make/run       — ispolnit plan (v AB=B zapisyvaem na fleshku)
  • GET  /admin/usb/verify         — proverka fleshki (manifest/sha256), ?mount=/path

Mosty:
- Yavnyy (Kibernetika v†" UX): odin ekran dlya sozdaniya po shagam «Proba→Plan→Sozdat» Re proverki.
- Skrytyy 1 (Infoteoriya v†" Vezopasnost): manifest s SHA256, ukladka tolko po knopke, AB-sloty dlya dry-run.
- Skrytyy 2 (Praktika v†" Sovmestimost): struktura sovmestima s verify/deploy bez pravok.

Zemnoy abzats:
Eto «sterilnaya perevyazochnaya»: pod rukoy nuzhnye instrumenty i antiseptiki (kheshi, manifest, README).
Polzovatel vybiraet fleshku, optsionalno ukazyvaet put k dampu.
Pered tem kak «nesti» nabor v operatsionnuyu — nazhimaem «Proverit», sveryaem plomby Re obemy, Re tolko posle — «Poekhali».
Nikakikh formatirovaniy/avtorana — tolko akkuratnaya ukladka v `/ESTER`.

# c=a+b
"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, render_template, request

# Ispolzuem bolee sovremennyy podkhod s planirovaniem i primeneniem
from modules.usb.usb_probe import list_targets
from modules.usb.portable_layout import build_plan, apply_plan
from modules.selfmanage.usb_verify import verify_usb  # Integriruem verifikatsiyu
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usb_make = Blueprint("usb_make", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()
DEF_LABEL = os.getenv("ESTER_USB_LABEL", "ESTER")
RELEASE_NAME = os.getenv("ESTER_RELEASE_NAME", "ester_release.tar.gz")

@bp_usb_make.get("/admin/usb/make")
def page_usb_make():
    """Otobrazhaet HTML-stranitsu mastera sozdaniya fleshki."""
    return render_template("usb_make.html", ab=AB, label=DEF_LABEL, release_name=RELEASE_NAME)

@bp_usb_make.get("/admin/usb/drives")
def api_list_drives():
    """Vozvraschaet JSON-spisok dostupnykh semnykh nositeley."""
    try:
        # list_targets - bolee novoe nazvanie iz odnogo iz variantov
        items = list_targets()
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500

@bp_usb_make.post("/admin/usb/make/plan")
def api_make_plan():
    """Prinimaet parametry i vozvraschaet plan sborki bez zapisi na disk."""
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    release = data.get("release") or None
    dump = data.get("dump") or None
    label = data.get("label") or DEF_LABEL
    compute_sha = bool(data.get("compute_sha", True))

    if not mount:
        return jsonify({"ok": False, "error": "mount-required"}), 400

    plan = build_plan(mount, release, dump, label=label, compute_sha=compute_sha)
    return jsonify({"ok": True, "plan": plan, "ab": AB})

@bp_usb_make.post("/admin/usb/make/run")
def api_make_run():
    """Vypolnyaet plan po zapisi faylov na fleshku. R' rezhime A - dry-run."""
    data = request.get_json(silent=True) or {}
    plan = data.get("plan") or {}
    # Esli AB rezhim ne 'B' ili yavno ukazan dry-run, to vypolnyaem vkholostuyu
    dry = (AB != "B") or bool(data.get("dry", False))

    if not plan:
        return jsonify({"ok": False, "error": "plan-required"}), 400

    report = apply_plan(plan, dry=dry)
    report["ab"] = AB
    return jsonify(report)

@bp_usb_make.get("/admin/usb/verify")
def api_usb_verify():
    """Proveryaet tselostnost struktury ESTER/ na ukazannom nositele."""
    mount = (request.args.get("mount") or "").strip()
    if not mount:
        return jsonify({"ok": False, "error": "mount-required"}), 400
    report = verify_usb(mount)
    return jsonify(report)

def register_usb_make(app, url_prefix: str | None = None) -> None:
    """R egistriruet vse marshruty dannogo modulya v prilozhenii Flask."""
    app.register_blueprint(bp_usb_make)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_make_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/make")
        def _p():
            return page_usb_make()

        @pref.get("/admin/usb/drives")
        def _pd():
            return api_list_drives()

        @pref.post("/admin/usb/make/plan")
        def _pl():
            return api_make_plan()

        @pref.post("/admin/usb/make/run")
        def _pr():
            return api_make_run()

        @pref.get("/admin/usb/verify")
        def _pv():
            return api_usb_verify()

# app.register_blueprint(pref)




def register(app):
    app.register_blueprint(bp_usb_make)
    return app