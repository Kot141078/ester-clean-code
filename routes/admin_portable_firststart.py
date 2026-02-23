# -*- coding: utf-8 -*-
"""
routes/admin_portable_firststart.py - «Pervyy start»: profil uzla, rekomendatsii ENV i Telegram-paket (offlayn).

Marshruty:
  • GET  /admin/portable/firststart            - stranitsa
  • GET  /admin/portable/firststart/status     - sys-profil + rekomendatsii + usb/ab
  • POST /admin/portable/firststart/apply      - zapisat profile.json + recommend.env (AB=A → dry)
  • POST /admin/portable/firststart/telegram   - sgenerirovat rukopozhatie (tekst + payload-fayl v outbox)

Mosty:
- Yavnyy (profil → konfig → svyaz): vse na odnom ekrane.
- Skrytyy 1 (Infoteoriya): yavnye, determinirovannye pravila rekomendatsiy → vosproizvodimost.
- Skrytyy 2 (Praktika): zapis tolko v ESTER/portable/* i payloads/outbox/*, offlayn, stdlib.

Zemnoy abzats:
Eto «master vklyucheniya»: srazu podskazyvaet «kakie ruchki krutit» i kak «pomakhat rukoy» drugim kopiyam cherez Telegram.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.portable.self_profile import detect_system, choose_recommendations, render_recommend_env, write_profile_and_env  # type: ignore
from modules.portable.peer_contact import build_handshake  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_portable_firststart", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _usb_present() -> bool:
    try:
        from modules.portable.env import detect_portable_root  # type: ignore
        return bool(detect_portable_root(None))
    except Exception:
        return False

@bp.get("/admin/portable/firststart")
def page():
    return render_template("admin_portable_firststart.html", ab=AB)

@bp.get("/admin/portable/firststart/status")
def status():
    sysinfo = detect_system()
    rec = choose_recommendations(sysinfo)
    env_text = render_recommend_env(sysinfo, rec)
    return jsonify({"ok": True, "ab": AB, "usb": _usb_present(), "system": sysinfo, "recommend": rec, "env_preview": env_text})

@bp.post("/admin/portable/firststart/apply")
def apply():
    sysinfo = detect_system()
    rec = choose_recommendations(sysinfo)
    res = write_profile_and_env(sysinfo, rec)
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res}), code

@bp.post("/admin/portable/firststart/telegram")
def telegram():
    meta = (request.get_json(silent=True) or {}).get("meta") or {}
    res = build_handshake(meta)
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res}), code

def register_admin_portable_firststart(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_portable_firststart_pref", __name__, url_prefix=url_prefix)
        @pref.get("/admin/portable/firststart")
        def _p(): return page()
        @pref.get("/admin/portable/firststart/status")
        def _s(): return status()
        @pref.post("/admin/portable/firststart/apply")
        def _a(): return apply()
        @pref.post("/admin/portable/firststart/telegram")
        def _t(): return telegram()
        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app