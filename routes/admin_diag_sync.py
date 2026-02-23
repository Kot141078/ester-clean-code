# -*- coding: utf-8 -*-
"""
routes/admin_diag_sync.py - UI/REST «Diag Sync (LAN)»: indeksy, vybor, fetch/merge, kross-tiket.

Marshruty:
  • GET  /admin/diag_sync
  • GET  /admin/diag_sync/status
  • POST /admin/diag_sync/cross_ticket   {names: ["2025-09-28.ndjson", ...]}

Zametki:
  • Spisok pirov chitaem iz lan_pkg_peers.json cherez /lan/packages/peers (esli paket LAN_Packages ustanovlen).
  • Fetch/merge vypolnyaetsya cherez /lan/diagnostics/fetch (edinaya logika).

Mosty:
- Yavnyy (UX ↔ Obmen): odin ekran - smotret indeksy, slivat istorii, zabirat tikety.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): podpis uzla vezde - legko filtrovat istochniki.
- Skrytyy 2 (Praktika ↔ Sovmestimost): reuse ACL/throttle; ta zhe skhema dry(A)/real(B).

Zemnoy abzats:
Eto «sborochnaya»: v paru klikov podtyanuli chuzhuyu telemetriyu, vlili v svoi fayly i sobrali obschiy tiket.

# c=a+b
"""
from __future__ import annotations
import io, json, os, time, zipfile
from pathlib import Path
from typing import Any, Dict, List
from flask import Blueprint, jsonify, render_template, request

from modules.diag.signature import get_signature  # type: ignore
from modules.diag.catalog import build_diag_index  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_diagui = Blueprint("admin_diag_sync", __name__)
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
DIAG_DIR  = STATE_DIR / "diagnostics"
HIST_DIR  = DIAG_DIR / "history"
TIC_DIR   = DIAG_DIR / "tickets"
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _read_peers() -> List[str]:
    # chitaem peers cherez fayl, esli est
    try:
        d = json.loads((STATE_DIR / "lan_pkg_peers.json").read_text(encoding="utf-8"))
        return [str(x) for x in d.get("items", []) if x]
    except Exception:
        return []

@bp_diagui.get("/admin/diag_sync")
def page():
    return render_template("diag_sync.html", ab=AB)

@bp_diagui.get("/admin/diag_sync/status")
def status():
    return jsonify({
        "ok": True, "ab": AB,
        "signature": get_signature(),
        "local": build_diag_index(),
        "peers": _read_peers()
    })

@bp_diagui.post("/admin/diag_sync/cross_ticket")
def cross_ticket():
    body = request.get_json(silent=True) or {}
    names = body.get("names") or []
    if not isinstance(names, list) or not names:
        return jsonify({"ok": False, "error": "names required"}), 400
    # Sbor ZIP: current_report + vybrannye history/*.ndjson
    ts = int(time.time())
    name = f"cross-ticket-{ts}.zip"
    outp = TIC_DIR / name
    outp.parent.mkdir(parents=True, exist_ok=True)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        # svezhiy otchet
        try:
            from modules.selfcheck.health_probe import build_report  # type: ignore
            cur = build_report(deep=True)
            z.writestr("current_report.json", json.dumps(cur, ensure_ascii=False, indent=2))
        except Exception:
            pass
        # vybrannye istorii
        for nm in names:
            p = (HIST_DIR / nm).resolve()
            if str(p).startswith(str(HIST_DIR.resolve())) and p.exists():
                try: z.write(p, arcname=f"history/{p.name}")
                except Exception: pass
    outp.write_bytes(buf.getvalue())
    return jsonify({"ok": True, "zip": str(outp)})

def register_admin_diag_sync(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_diagui)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_diag_sync_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/diag_sync")
        def _p(): return page()

        @pref.get("/admin/diag_sync/status")
        def _s(): return status()

        @pref.post("/admin/diag_sync/cross_ticket")
        def _ct(): return cross_ticket()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_diagui)
    return app